from __future__ import division
import krpc
import vlc
import time
import random
import yaml
import os
import socket
import math

class Player(object):
    def __init__(self, path, preload=True, poll_rate=1):
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.preload = preload
        self.tracks = self.parse_tracks(path)
        self.conn = krpc.connect(name="Music Player")
        self.tracks_played = {scene:0 for scene in self.tracks}
        self.poll_rate = poll_rate
        self.current_scene = "SpaceCenter"

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
            # altitude = self.conn.add_stream(getattr, vessel.flight(), 'mean_altitude')
            try:
                with self.conn.stream(getattr, vessel.flight(), "mean_altitude") as altitude:
                    while altitude() < current_body.atmosphere_depth:
                        if self.player.is_playing():
                            self.player.stop()

                    while altitude() >= current_body.atmosphere_depth:
                        if not self.player.is_playing():
                            self.play_next_track("Space")

                        if vessel.parts.controlling.docking_port:
                            self.player.stop()
                            self.play_next_track("Docking")
                            while vessel.parts.controlling.docking_port:
                                if not self.player.is_playing():
                                    self.play_next_track("Docking")
                                time.sleep(self.poll_rate * 0.25)
                            self.fade_out(1.5)

                        if self.conn.space_center.target_vessel:
                            distance = math.sqrt(sum([i**2 for i in (self.conn.space_center.target_vessel.position(self.conn.space_center.active_vessel.reference_frame))]))
                            if distance < 1000:
                                self.fade_out(1.5)
                                self.play_next_track("Rendezvous")
                                try:
                                    with self.conn.stream(vessel.position, self.conn.space_center.target_vessel.reference_frame) as position:
                                        while math.sqrt(sum([i**2 for i in position()])) < 1000:
                                            if not self.player.is_playing():
                                                self.play_next_track("Rendezvous")
                                except AttributeError:
                                    continue
                                finally:
                                    self.fade_out(1.5)
                                    
            except krpc.error.RPCError:
                continue

    def play_track(self, track):
        self.player.set_media(track)
        if self.player.play() == -1:
            print("Couldn't play a file. Skipping.")
            return False
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
                result[k] = []
                try:
                    random.shuffle(stuff[k])
                    for v in stuff[k]:
                        if not os.path.exists(v):
                            print("{}: {} not found.".format(k, v))
                        elif os.path.isfile(v):
                            if self.preload:
                                result[k].append(self.load_track(v))
                            else:
                                result[k].append(v)
                        elif os.path.isdir(v):
                            for f in os.listdir(v):
                                if self.preload:
                                    result[k].append(self.load_track(os.path.join(v, f)))
                                else:
                                    result[k].append(os.path.join(v, f))
                except TypeError:
                    print("No music in {}.".format(k))
                    
        return result
                    
def main():
    config_path = "music.yaml"
    player = Player(config_path)
    player.play()

if __name__ == "__main__":
    main()
