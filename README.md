# Music Hack for Kerbal Space Program
A Python script for playing music for KSP that's a step above muting the game's music and playing your own, but a step below a proper mod.
Controls VLC based on events that occur in-game using [KRPC](https://github.com/krpc/krpc).

## Features
- As an external program, no impact on game memory usage
- Can play anything that VLC can play, such as Youtube URLs
- Can play dramatic music during docking or rendezvous a la _Interstellar_
- Play custom music while editing, above the atmosphere, at the space center, or at the tracking station, eg play the Normandy galaxy map theme at the tracking center
- Configurable via ```music.yaml```
- Comes with stock music

## Requirements
- Python 2.7 or later
- LibVLC for Python (```pip install python-vlc```) - currently only supports 32 bit python
- KRPC (```pip install krpc```)
- PyYAML (```pip install PyYAML```)

## Usage
- Edit ```music.yaml``` 
    - Individual files or directories with music inside are allowed
    - To disable music for a label, just delete all the bullets underneath it
    - Backslashes must be doubled for Windows style paths
- Start KSP
- Mute KSP music
- Load game
- Start KRPC server (or set to autostart)
- Run the program (```python music_hack.py``` or ```./music_hack.py```)
- Accept connection from KSP (or set KRPC server to auto-accept)
- Crashes of the music player only require a restart of the music player

## Limitations
- Can only distinguish the tracking center. The rest of the space center scenes all play music from the space center label.
- Could not locate stock tracking station music
- Can't play KSP theme when the program launches
- Youtube playback depends on whether LibVLC has up-to-date Youtube capabilities.
- Space music continues after switch to space center till next scene change.

## Licensing
Music tracks by [Kevin MacLeod](incompetech.com)
Licensed under Creative Commons: [By Attribution 3.0 License](http://creativecommons.org/licenses/by/3.0/)

Original birdsong ambience by [dobroide](http://www.freesound.org/people/dobroide/)
Licensed under Creative Commons: [By Attribution 3.0 License](http://creativecommons.org/licenses/by/3.0/)

The rest of this is under [GPL v3](http://www.gnu.org/licenses/quick-guide-gplv3.html).
