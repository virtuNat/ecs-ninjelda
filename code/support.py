# Support classes and functions.
import json
from enum import Enum, auto
from pathlib import Path
from dataclasses import InitVar, dataclass, field
from typing import Any, Optional, TypedDict, Callable

import pygame as pg
from pygame.math import Vector2 as Vec2d

import ecs
from ecs.pygame import FrameData, SpriteComponent
import settings

_anims = {}

def load_image(
    path: Path | str, scaling: float = 1.0,
    colorkey: Optional[pg.Color] = None, is_alpha: bool = False
    ) -> pg.Surface:
    """"""
    surf = pg.image.load(str(path))
    if not is_alpha:
        surf.convert()
        if colorkey is not None:
            surf.set_colorkey(colorkey)
    else:
        surf.convert_alpha()
    w, h = surf.get_size()
    return pg.transform.scale(surf, (round(w * scaling), round(h * scaling)))

def load_anim(fname: str) -> dict[str: FrameData]:
    """"""
    try:
        return _anims[fname]
    except KeyError:
        with open(settings.ASSET_PATHS.anim_path/f'{fname}.json') as animfile:
            anim = json.loads(animfile.read())
        _anims[fname] = anim
        return anim


class Actions(Enum):
    """"""
    attack = auto()
    magic = auto()
    jump = auto()
    switch_weapon_up = auto()
    switch_weapon_down = auto()
    switch_magic_up = auto()
    switch_magic_down = auto()


class FacingDir(Enum):
    """"""
    right = auto()
    down = auto()
    left = auto()
    up = auto()


class AttrDict(dict):
    """"""
    def __getattr__(self, name: str) -> Any:
        return super().__getitem__(name)


@dataclass
class Hitbox(ecs.Component):
    """"""
    hitbox: pg.Rect
    pos_at: str = 'center'
    pos_from: Callable[[SpriteComponent], tuple[int, int] | Vec2d] = lambda s: s.rect.center

    def set_pos(self, value):
        setattr(self.hitbox, self.pos_at, self.pos_from(value))


@dataclass
class CameraComponent(ecs.Component):
    """Marks an entity as having a large sprite that need not all be rendered."""

    def __init_entity__(self):
        sprite = self.scene.get_component(self.entity, SpriteComponent)
        sprite.area.size = self.scene.get_window().rect.size


class OffsetComponent(ecs.Component):
    """Marks if an entity can be moved by the scrolling camera."""


class OffsetSystem(ecs.System):
    offset = Vec2d()

    def update(self, scene: ecs.Scene, dt: int) -> None:
        """"""
        if self.offset.magnitude() == 0:
            return
        rects = []
        for eid, _ in scene.get_entities_with(OffsetComponent):
            sprite, cam, hitbox = scene.try_components(eid, SpriteComponent, CameraComponent, Hitbox)
            if sprite is not None:
                rects.append(sprite.rect.copy())
                sprite.rect.topleft += self.offset
                sprite.dirty = True
                if cam is not None:
                    sprite.area.topleft += self.offset
            if hitbox is not None:
                hitbox.hitbox.topleft += self.offset
        scene.update_rects(rects)
        self.__class__.offset *= 0
