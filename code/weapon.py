# Weapon sprites.
from __future__ import annotations

import json
from dataclasses import InitVar, dataclass, field
from typing import Optional, TypedDict, Callable

import pygame as pg
from pygame.math import Vector2 as Vec2d

import ecs
from ecs.pygame import SpriteComponent, EventComponent, SpriteGroup
from support import load_image, Actions, FacingDir
from settings import ASSET_PATHS, DISPLAY, KEY_CONFIG

Weapon = TypedDict('Weapon',
    name=str,
    damage=int,
    attack_time=int,
    attack_cd=int,
    ranged=bool,
    scaling=str,
    surfs=dict[str, pg.Surface],
    )

_weapons: dict[str, Weapon] = {}
_weapon_pos_at: dict[FacingDir, Callable[[pg.Rect], dict[str, tuple[int, int] | Vec2d]]] = {
    FacingDir.down:  lambda r: {'midtop'   : r.midbottom + Vec2d(-3, 0) * DISPLAY.scaling},
    FacingDir.right: lambda r: {'midleft'  : r.midright  + Vec2d( 0, 4) * DISPLAY.scaling},
    FacingDir.up:    lambda r: {'midbottom': r.midtop    + Vec2d(-3, 0) * DISPLAY.scaling},
    FacingDir.left:  lambda r: {'midright' : r.midleft   + Vec2d( 0, 4) * DISPLAY.scaling},
    }

def load_weapon(name) -> Weapon:
    """"""
    try:
        return _weapons[name]
    except KeyError:
        with open(ASSET_PATHS.data_path/'weapons'/f'{name}.json') as weaponfile:
            weapon = json.loads(weaponfile.read())
            weapon['name'] = name

            surf = load_image(
                ASSET_PATHS.graphics_path/'weapons'/name/'SpriteInHand.png',
                scaling=DISPLAY.scaling,
                is_alpha=True,
                )
            surf_rot = pg.transform.rotate(surf, 90)
            weapon['surfs'] = {
                FacingDir.down : surf,
                FacingDir.right: surf_rot,
                FacingDir.up   : pg.transform.flip(surf, False, True),
                FacingDir.left : pg.transform.flip(surf_rot, True, False),
                }
        _weapons[name] = weapon
        return _weapons[name]

def create_weapon(actor: ecs.Component, name: str = 'fist', layer: int = 0) -> tuple[SpriteComponent, WeaponComponent]:
    """"""
    weapon_data = load_weapon(name)
    weapon = WeaponComponent(actor, name)
    sprite = SpriteComponent(
        weapon_data['surfs'][FacingDir.down],
        layer=layer,
        always_dirty=False,
        dirty=False,
        is_visible=False,
        )
    return sprite, weapon


@dataclass
class WeaponComponent(EventComponent):
    """"""
    actor: ecs.Component
    name: InitVar[str] = 'fist'

    weapon: Weapon = field(init=False)

    def __init_entity__(self, name) -> None:
        self.weapon = load_weapon(name)
        self.apply_weapon()

    def __getattr__(self, name: str) -> Any:
        try:
            return self.weapon[name]
        except KeyError:
            return super().__getattr__(name)

    def apply_weapon(self, actor: Optional[ecs.Component] = None) -> None:
        """"""
        if actor is None:
            actor = self.actor

        actor.attack_time = self.weapon['attack_time']
        actor.attack_cd = self.weapon['attack_cd']

    def set_sprite(self) -> None:
        """"""
        facing = self.actor.facing
        sprite = self.scene.get_component(self.actor.entity, self.actor.sprite_cls)
        weapon = self.scene.get_component(self.entity, SpriteComponent)

        weapon.surf = self.weapon['surfs'][facing]
        weapon.area = weapon.surf.get_rect()
        weapon.rect = weapon.surf.get_rect(**_weapon_pos_at[facing](sprite.rect))
        weapon.is_visible = True
        weapon.dirty = True

    @EventComponent.listener(pg.KEYDOWN)
    def on_key_pressed(self, event: pg.event.EventType) -> None:
        """Callback when keyboard key is pressed."""
        if event.key not in KEY_CONFIG:
            return
        action = KEY_CONFIG[event.key]
        if action == Actions.attack and self.actor.attacking == self.actor.attack_time:
            self.apply_weapon()
            self.set_sprite()
        elif action == Actions.switch_weapon_up:
            pass
        elif action == Actions.switch_weapon_down:
            pass


class WeaponSystem(ecs.System):
    """"""
    def update(self, scene: ecs.Scene, dt: int) -> None:
        window = scene.get_window()
        for eid, (sprite, weapon) in scene.get_entities_with(SpriteComponent, WeaponComponent):
            if weapon.actor.resting == weapon.attack_cd:
                sprite.is_visible = False
                scene.update_rects([sprite.rect])
