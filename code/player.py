# Player.
from dataclasses import InitVar, dataclass, field
from typing import Optional

import pygame as pg
from pygame.math import Vector2 as Vec2d

import ecs
from ecs.pygame import EventComponent, SpriteComponent, AnimationComponent
from support import (
    load_image, load_anim,
    Actions, FacingDir,
    Hitbox, OffsetSystem,
    )
from settings import ASSET_PATHS, DISPLAY, KEY_CONFIG

MOVE_MAP = {
    FacingDir.right: ('x', +1),
    FacingDir.down: ('y', +1),
    FacingDir.left: ('x', -1),
    FacingDir.up: ('y', -1),
    }

def create_player(
    scene: ecs.Scene,
    pos: tuple[int, int] | Vec2d = (0, 0),
    pos_at: str = 'center',
    ) -> ecs.Entity:
    """"""
    player = scene.create_entity(
        (psprite := SpriteComponent(
            load_image(
                ASSET_PATHS.sprites_path/'princess_sprite.png',
                scaling=DISPLAY.scaling,
                is_alpha=True,
                ),
            pg.Rect((0, 0), Vec2d(16) * DISPLAY.scaling),
            layer=3,
            always_dirty=False,
            pos=scene.get_window().rect.center,
            )),
        AnimationComponent(
            Vec2d(16) * DISPLAY.scaling,
            load_anim('actor'),
            ),
        PlayerComponent(),
        (phitbox := Hitbox(
            pg.Rect((0, 0), Vec2d(14, 10) * DISPLAY.scaling),
            pos_at='center',
            pos_from=lambda s: s.rect.center
            )),
        )

    OffsetSystem.offset = Vec2d(scene.get_window().rect.center) - getattr(phitbox.hitbox, phitbox.pos_at) - pos
    OffsetSystem().update(scene, 0)
    phitbox.set_pos(psprite)
    return player


@dataclass
class BoundingBox(ecs.Component):
    """"""
    margin: InitVar[tuple[int, int]]

    bounds: pg.Rect = field(init=False)

    def __init_entity__(self, margin) -> None:
        dx, dy = margin
        window = self.scene.get_window()
        if isinstance(dx, float):
            dx = round(window.rect.w * dx / 2) << 1
        if isinstance(dy, float):
            dy = round(window.rect.h * dy / 2) << 1
        self.bounds = window.rect.inflate(-dx, -dy)

    def enforce_bounds(self, rect: pg.Rect) -> Vec2d:
        pos = Vec2d(rect.topleft)
        rect.clamp_ip(self.bounds)
        return rect.topleft - pos


@dataclass
class PlayerComponent(EventComponent):
    """
    """
    sprite_cls:  type = SpriteComponent

    facing: FacingDir = field(default=FacingDir.down, init=False)
    move_stack:  list = field(default_factory=list, init=False)

    pos:        Vec2d = field(init=False)
    moving:     Vec2d = field(default_factory=Vec2d, init=False)

    speed:        int = field(default=6, init=False)
    attack_time:  int = field(default=12, init=False)
    attack_cd:    int = field(default=13, init=False)

    attacking:    int = field(default=0, init=False)
    resting:      int = field(default=0, init=False)    

    def __init_entity__(self):
        sprite = self.scene.get_component(self.entity, self.sprite_cls)
        self.pos = Vec2d(getattr(sprite.rect, sprite.pos_at))

    def get_velocity(self) -> Vec2d:
        if self.attacking > 0:
            return Vec2d()
        return self.speed * self.moving.normalize()
    
    @EventComponent.listener(pg.KEYDOWN)
    def on_key_pressed(self, event: pg.event.EventType) -> None:
        """Callback when keyboard key is pressed."""
        if event.key not in KEY_CONFIG:
            return
        action = KEY_CONFIG[event.key]
        if isinstance(action, FacingDir):
            if self.attacking <= 0:
                self.facing = action
            self.move_stack.append(action)
            setattr(self.moving, *MOVE_MAP[self.move_stack[-1]])
        elif action is Actions.attack and self.resting <= 0:
            self.attacking = self.attack_time
            self.resting = self.attack_time + self.attack_cd

    @EventComponent.listener(pg.KEYUP)
    def on_key_released(self, event: pg.event.EventType) -> None:
        """Callback when keyboard key is released."""
        if event.key not in KEY_CONFIG:
            return
        action = KEY_CONFIG[event.key]
        if isinstance(action, FacingDir):
            setattr(self.moving, MOVE_MAP[action][0], 0)
            self.move_stack.remove(action)
            if self.move_stack:
                if self.attacking <= 0:
                    self.facing = self.move_stack[-1]
                setattr(self.moving, *MOVE_MAP[self.move_stack[-1]])


@dataclass
class PlayerSystem(ecs.System):
    """
    """
    sprite_cls: type = SpriteComponent
    anim_cls: type = AnimationComponent

    def update(self, scene: ecs.Scene, dt: int) -> None:
        """Update player state."""
        sprite, anim, event, hitbox = scene.get_components(
            scene.player, self.sprite_cls, self.anim_cls, PlayerComponent, Hitbox
            )
        # By default, set animation to idle.
        anim_name = event.facing.name
        # If attacking, change animation to attacking.
        if event.attacking > 0:
            event.attacking -= 1
            anim_name = f'atk_{event.facing.name}'
        else:
            # Once attacking ends, resume control of movement.
            if event.move_stack:
                event.facing = event.move_stack[-1]
            # Move the player sprite and change animation to moving if moving.
            if event.moving.magnitude() > 0:
                # Prevent artifacts at the sprite's old position.
                scene.update_rects([sprite.rect.copy()])
                # Update animation state.
                anim_name = f'move_{event.facing.name}'
                sprite.dirty = True
                # Update position based on velocity.
                velocity = event.get_velocity()
                event.pos += velocity
                # Check for collisions.
                rects = {
                    e: h.hitbox
                    for e, (h,) in scene.get_entities_with(Hitbox)
                    }
                del rects[scene.player]
                hit_rect = hitbox.hitbox
                # Horizontal collision test
                if abs(velocity.x) > 0:
                    collided = False
                    hit_rect.centerx = event.pos.x
                    for rect in rects.values():
                        if hit_rect.colliderect(rect):
                            collided = True
                            if velocity.x > 0:
                                hit_rect.right = rect.left
                            else:
                                hit_rect.left = rect.right
                    if collided:
                        event.pos.x = getattr(hit_rect, hitbox.pos_at)[0]
                # Vertical collision test
                if abs(velocity.y) > 0:
                    collided = False
                    hit_rect.centery = event.pos.y
                    for rect in rects.values():
                        if hit_rect.colliderect(rect):
                            collided = True
                            if velocity.y > 0:
                                hit_rect.bottom = rect.top
                            else:
                                hit_rect.top = rect.bottom
                    if collided:
                        event.pos.y = getattr(hit_rect, hitbox.pos_at)[1]
                # Enforce bounding box.
                bounds = scene.get_single_component(BoundingBox)
                offset = bounds.enforce_bounds(hit_rect)
                if offset.magnitude() > 0:
                    event.pos += offset
                    OffsetSystem.offset = offset
                # Adjust display position accordingly.
                setattr(sprite.rect, sprite.pos_at, event.pos)
        # Manage action cooldown timer.
        if event.resting > 0:
            event.resting -= 1
        # Change animation only if the animation is different.
        if anim.curr_anim != anim_name:
            anim.curr_anim = anim_name
            anim.index = 0
            sprite.area.topleft = anim.get_pos()
            sprite.dirty = True
        
