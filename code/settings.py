# Settings and configuration stuff.
from pathlib import Path
from configparser import ConfigParser

import pygame as pg

from support import AttrDict, Actions, FacingDir

ASSET_PATHS = AttrDict()
DISPLAY = AttrDict()
KEY_CONFIG = AttrDict()


class Settings(object):
    __slots__ = ('_path', '_parser')

    def __init__(self, path: str | Path) -> None:
        self._path = path
        self._parser: ConfigParser = ConfigParser(
            converters={'resolution': lambda r: tuple(map(int, r.split('x')))}
            )
        self._parser.read(path)

    def __enter__(self):
        for path_name, path in self._parser['ASSET_PATHS'].items():
            ASSET_PATHS[path_name] = Path(path)

        display = self._parser['DISPLAY']
        DISPLAY['resolution'] = display.getresolution('resolution', (1280, 760))
        DISPLAY['display_flags'] = display.getint('display_flags', pg.SHOWN)
        DISPLAY['scaling'] = display.getfloat('scaling', 1.0)
        DISPLAY['framerate'] = display.getint('framerate', 60)
        DISPLAY['doublebuf'] = display.getboolean('doublebuf', True)
        DISPLAY['vsync'] = display.getboolean('vsync', True)

        for action, keybind in self._parser['KEY_CONFIG'].items():
            try:
                key = pg.key.key_code(keybind)
            except ValueError:
                continue
            if action in Actions.__members__:
                action = Actions[action]
            elif action in FacingDir.__members__:
                action = FacingDir[action]
            else:
                continue
            KEY_CONFIG[key] = action

        return self

    def __exit__(self, exc_type, exc_value, exc_trace):
        display = self._parser['DISPLAY']
        for setting, value in DISPLAY.items():
            if setting != 'resolution':
                display[setting] = str(value)
            else:
                display[setting] = 'x'.join(map(str, value))

        key_config = self._parser['KEY_CONFIG']
        for keybind, action in KEY_CONFIG.items():
            key_config[action.name] = pg.key.name(keybind)

        with open(self._path, 'w') as config_file:
            self._parser.write(config_file)
