#!/usr/bin/env python3
import sys
from pathlib import Path

import pygame as pg
from pygame.math import Vector2 as Vec2d

import ecs
from ecs.pygame import (
    EventComponent, EventSystem, WindowComponent,
    SortedGroup, AnimationSystem,
    PygameScene, PygameGame,
    )
from settings import DISPLAY, DEBUG, Settings
from support import OffsetSystem
from tilemap import load_map, load_player_from
from player import BoundingBox, PlayerComponent, PlayerSystem
from weapon import create_weapon, WeaponSystem

__title__ = 'Ninjelda'
__version__ = '1.0.0'
__author__ = 'virtuNat'


class ExitComponent(EventComponent):
    """Component to ensure that the close button in the window works."""
    
    @EventComponent.listener(pg.QUIT)
    def on_close_window(self, event):
        pg.quit()
        sys.exit()


class NinjeldaScene(PygameScene):
    """The Scene present during normal play."""

    def __init__(self, *args, map_name: str = 'default_map', **kwargs):
        super().__init__(*args, **kwargs)
        # Add Components
        load_map(self, map_name)
        self.player = load_player_from(self, map_name)
        self.create_entity(ExitComponent())
        self.create_entity(BoundingBox((0.4, 0.4)))
        self.create_entity(*create_weapon(
            self.get_component(self.player, PlayerComponent),
            name='naginata',
            layer=3,
            ))

        # Add Systems
        self.add_systems((
            (EventSystem([pg.QUIT, pg.KEYDOWN, pg.KEYUP]), 256),
            (PlayerSystem(), 20),
            (OffsetSystem(), 15),
            (WeaponSystem(), 10),
            (AnimationSystem(), 10),
            (SortedGroup(key=lambda s: (s.layer, s.rect.bottom)), 0),
            ))


class Ninjelda(PygameGame):
    """"""
    
    def __init__(self):
        super().__init__(fps=DISPLAY.framerate)
        pg.display.set_caption(__title__)
        self.set_scene(NinjeldaScene(
            WindowComponent(
                size=DISPLAY.resolution,
                flags=DISPLAY.display_flags,
                vsync=DISPLAY.vsync,
                ),
            is_opengl=pg.OPENGL & DISPLAY.display_flags,
            doublebuf=DISPLAY.doublebuf,
            ))


if __name__ == '__main__':
    if DEBUG:
        import cProfile
        import pstats

        with Settings(Path('.')/'config.ini') as settings:
            cProfile.run('Ninjelda().run()', 'game_profile')
        stats = pstats.Stats('ninjelda.profile')
        stats.strip_dirs()
        stats.sort_stats(pstats.SortKey.CUMULATIVE)
        stats.print_stats(100)
    else:
        Ninjelda().run()
