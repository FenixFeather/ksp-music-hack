#!/usr/bin/env python
from __future__ import division
import krpc
import vlc
import time
import random
import yaml
import os
import socket
import math
import logging
import sys
from collections import deque

class Player(object):
    def __init__(self, path, preload=True):
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.preload = preload
        self.config = {}
        self.tracks = self.parse_tracks(path)
        self.conn = None
        self.tracks_played = {scene:0 for scene in self.tracks}
        self.poll_rate = self.config["poll_rate"]
        self.current_scene = "SpaceCenter"

    def can_connect(self):
        address = (self.config["address"], self.config["rpc_port"])
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.connect(address)
            s.shutdown(socket.SHUT_RDWR)
            s.close()
            return True
        except Exception as e:
            logging.debug(e)
            return False

    def wait_for_server(self):
        gamelog = GameLog(self.config["gamelog"], self.config["poll_rate"])

        gamelog.wait_for_game_start()
        
        while True:
            if self.can_connect() or gamelog.loaded_save():
                self.player.stop()
                logging.info("Save game loaded.")
                return

            if gamelog.loaded():
                self.player.stop()
                self.play_next_track("MainMenu")
                logging.info("Main Menu reached")

            logging.debug("Game still loading.")
            time.sleep(self.poll_rate / 10)

    def connect(self, name="Music Player"):
        self.conn = krpc.connect(name=name,
                                 address=self.config["address"],
                                 rpc_port=self.config["rpc_port"],
                                 stream_port=self.config["stream_port"])

    def get_current_scene(self):
        try:
            self.conn.space_center.active_vessel
            return "Flight", True
        except (OSError, socket.error, KeyboardInterrupt):
            print("Lost connection.")
            return None, True
        except krpc.error.RPCError as e:
            try:
                scene = str(e)[str(e).index("'") + 1:str(e).rindex("'")]
                return scene, self.current_scene != scene
            except:
                return "SpaceCenter", self.current_scene != scene

    def play(self):
        while True:
            try:
                self.current_scene, changed = self.get_current_scene()

                if not self.current_scene:
                    return

                if self.current_scene == "Flight":
                    self.play_flight_music()
                else:
                    self.play_scene_music(changed)

                time.sleep(self.poll_rate)
            except (OSError, socket.error, KeyboardInterrupt):
                print("Connection lost.")
                return

    def select_track(self, scene):
        """"Handle avoiding repetition of tracks and empty playlists."""
        try:
            total_tracks = len(self.tracks[scene])
        except KeyError:
            return None
        
        if not total_tracks:
            return None
            
        if self.tracks_played[scene] == total_tracks:
            last = self.tracks[scene][-1]
            self.tracks[scene] = random.sample(self.tracks[scene][:-1], total_tracks - 1)
            self.tracks[scene].append(last)
            self.tracks_played[scene] = 0

        result = self.tracks[scene][self.tracks_played[scene]]

        self.tracks_played[scene] += 1
        
        if not self.preload:
            result = self.load_track(result)
        
        return result

    def play_next_track(self, scene):
        while True:
            next_track = self.select_track(scene)

            if not next_track:
                return

            if self.play_track(next_track):
                return

    def play_scene_music(self, changed):
        if changed:
            self.player.stop()

        if not self.player.is_playing():
            self.play_next_track(self.current_scene)

    def play_flight_music(self):
        self.player.stop()
        
        while True:
            self.current_scene, changed = self.get_current_scene()
            
            if self.current_scene != "Flight":
                return

            vessel = self.conn.space_center.active_vessel
            current_body = vessel.orbit.body
            # We're going to switch away from polling here to
            # avoid unnecessary requests. We need to keep an eye
            # out for the transitioning outside of the atmosphere

            try:
                with self.conn.stream(getattr, vessel.flight(), "mean_altitude") as altitude:
                    while altitude() < current_body.atmosphere_depth:
                        if self.player.is_playing():
                            self.player.stop()

                    while altitude() >= current_body.atmosphere_depth:
                        if not self.player.is_playing():
                            self.play_next_track("Space")

                        if vessel.parts.controlling.docking_port and self.tracks["Docking"]:
                            self.player.stop()
                            self.play_next_track("Docking")
                            while vessel.parts.controlling.docking_port:
                                if not self.player.is_playing():
                                    self.play_next_track("Docking")
                                time.sleep(self.poll_rate * 0.25)
                            self.fade_out(1.5)

                        if self.conn.space_center.target_vessel and self.tracks["Rendezvous"]:
                            distance = math.sqrt(sum([i**2 for i in (self.conn.space_center.target_vessel.position(self.conn.space_center.active_vessel.reference_frame))]))
                            if distance < 1000:
                                self.fade_out(1.5)
                                self.play_next_track("Rendezvous")
                                try:
                                    with self.conn.stream(vessel.position, self.conn.space_center.target_vessel.reference_frame) as position:
                                        while math.sqrt(sum([i**2 for i in position()])) < 1000:
                                            if not self.player.is_playing():
                                                self.play_next_track("Rendezvous")
                                            if not self.conn.space_center.target_vessel:
                                                break
                                except AttributeError:
                                    continue
                                finally:
                                    self.fade_out(1.5)
                                    
            except krpc.error.RPCError:
                continue

    def play_track(self, track):
        self.player.set_media(track)
        if self.player.play() == -1:
            logging.warning("Couldn't play a file. Skipping.")
            return False
        logging.info("Playing {}.".format(track.get_mrl()))
        time.sleep(self.poll_rate)
        return True

    def fade_out(self, seconds):
        starting_volume = self.player.audio_get_volume()
        sleep_increment = seconds / starting_volume

        for i in range(starting_volume):
            self.player.audio_set_volume(max(int(starting_volume - i), 1))
            time.sleep(sleep_increment)

        self.player.pause()
        self.player.audio_set_volume(int(starting_volume))
        self.player.stop()

    def load_track(self, path):
        if path[0:4] != "http":
            return self.instance.media_new(os.path.abspath(path))
        return self.instance.media_new(path)

    def parse_tracks(self, path):
        result = {}

        with open(path) as text:
            stuff = yaml.load(text)
            for k in stuff:
                if k in ["gamelog", "address", "rpc_port", "stream_port", "poll_rate"]:
                    self.config[k] = stuff[k]
                    continue
                    
                result[k] = []
                try:
                    for v in stuff[k]:
                        if os.path.isfile(v) or v[0:4] == "http":
                            if self.preload:
                                result[k].append(self.load_track(v))
                            else:
                                result[k].append(v)
                        elif os.path.isdir(v):
                            for f in os.listdir(v):
                                if os.path.isfile(os.path.join(v,f)):
                                    if self.preload:
                                        result[k].append(self.load_track(os.path.join(v, f)))
                                    else:
                                        result[k].append(os.path.join(v, f))
                        else:
                            logging.warning("{}: {} not found.".format(k, v))
                            
                    logging.info("{}: {} tracks loaded".format(k, len(result[k])))
                    random.shuffle(result[k])
                except TypeError:
                    logging.warning("No music in {0}. Disabling music for {0}.".format(k))
                    
        return result

class GameLog(object):
    def __init__(self, path, poll_rate, maxlen=10):
        self.size = os.path.getsize(path)
        self.path = path
        self.valid = (path is not None) and os.path.isfile(path)
        if not self.valid:
            logging.warning("Invalid gamelog path!")
        self.loaded_flag = False
        self.size_history = deque(range(maxlen), maxlen=maxlen)
        self.poll_rate = poll_rate
        self.update_size()

    def wait_for_game_start(self):
        logging.info("Waiting for game start...")
        if self.valid:
            while True:
                self.update_size()
                if self.get_diff() != 0:
                    logging.info("Game started.")
                    return
                time.sleep(self.poll_rate)
        
    def loaded(self):
        """Return True only once after loaded."""
        self.update_size()
        lines = self.get_changed_lines()
        
        if self.valid and not self.loaded_flag:
            for line in lines:
                if "Scene Change : From LOADING to MAINMENU" in line:
                    self.loaded_flag = True
                    return True
            if all([i == self.size_history[0] for i in self.size_history]):
                logging.info("Log hasn't changed for a while. Assume loaded.")
                self.loaded_flag = True
                return True
            
        return False

    def loaded_save(self):
        self.update_size()
        lines = self.get_changed_lines()

        if self.valid:
            for line in lines:
                if "Scene Change : From MAINMENU to SPACECENTER" in line:
                    return True

        return False

    def update_size(self):
        if self.valid:
            self.size_history.append(os.path.getsize(self.path))

    def get_size(self):
        return self.size_history[-1]

    def get_diff(self):
        return self.size_history[-1] - self.size_history[-2]

    def get_changed_lines(self):
        if self.valid:
            with open(self.path, 'r') as log:
                log.seek(self.get_diff(), 2)
                return log.readlines()
        
def main():
    logging.basicConfig(level=logging.INFO if "-v" in sys.argv else (logging.DEBUG if "-vv" in sys.argv else logging.WARNING))
    config_path = "music.yaml"
    try:
        player = Player(config_path)
        player.wait_for_server()
        player.connect()
        player.play()
    except KeyboardInterrupt:
        print("Quit.")

if __name__ == "__main__":
    main()
