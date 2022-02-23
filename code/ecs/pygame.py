"""Pygame engine using ECS implementation."""
from __future__ import annotations

import sys
from dataclasses import KW_ONLY, InitVar, dataclass, field
from collections import OrderedDict, defaultdict
from operator import attrgetter
from itertools import count, chain
from copy import deepcopy
from weakref import WeakValueDictionary
from types import MethodType
from typing import Any, Optional, Iterable, Callable, Generator, TypedDict

import pygame as pg
from pygame.math import Vector2 as Vec2d
import ecs

Callback = Callable[[ecs.Component, pg.event.EventType], None]
CallbackMethod = Callable[[pg.event.EventType], None]
RegisteredCallbackDict = dict[type, dict[int, Callback]]
RegisteredInstanceDict = defaultdict[int, WeakValueDictionary[int, 'EventComponent']]


class EventMeta(type):
    """
    """
    _registered: RegisteredCallbackDict = {}
    _instances:  RegisteredInstanceDict = defaultdict(WeakValueDictionary)

    def __new__(meta, name: str, bases: tuple[type, ...], attrs: dict[str, Any]) -> EventMeta:
        """
        """
        cls = super().__new__(meta, name, bases, attrs)
        listeners = {}
        for value in attrs.values():
            if (event_type := getattr(value, '__event_type__', None)) is None:
                continue
            listeners[event_type] = value
        if listeners:
            cls._registered[cls] = listeners
        return cls

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """
        """
        instance = super().__call__(*args, **kwargs)
        if cls in cls._registered:
            for event_type, name in cls._registered[cls].items():
                cls._instances[event_type][id(instance)] = instance
        return instance

    @classmethod
    def get_callbacks(meta, event_type: int) -> Generator[CallbackMethod, None, None]:
        """
        """
        for instance in meta._instances[event_type].values():
            yield MethodType(meta._registered[type(instance)][event_type], instance)


class EventComponent(ecs.Component, metaclass=EventMeta):
    """
    """
    @staticmethod
    def listener(event_type: int) -> Callable[[Callback], Callback]:
        """
        """
        def listener_decorator(func: Callback) -> Callback:
            func.__event_type__ = event_type
            return func
        return listener_decorator


@dataclass
class EventSystem(ecs.System):
    """
    System that performs Pygame event handling that can be used to configure the
    event queue through filtering in or out the event types that are desired.
    """
    event_types: InitVar[Optional[list[int]]] = None
    _: KW_ONLY
    is_included: InitVar[bool] = True
    pump: bool = True

    def __post_init__(self, event_types, is_included) -> None:
        pg.event.set_blocked(None)
        if event_types is None:
            return
        if is_included:
            pg.event.set_allowed(event_types)
        else:
            pg.event.set_blocked(event_types)

    def update(self, scene: ecs.Scene, dt: int) -> None:
        for event in pg.event.get(pump=self.pump):
            for callback in EventMeta.get_callbacks(event.type):
                callback(event)


@dataclass
class WindowComponent(ecs.Component, metaclass=ecs.Singleton):
    """
    Pygame Window component, representing the display window GUI.
    """
    size: InitVar[tuple[int, int]] = (0, 0)
    flags: InitVar[int] = 0
    depth: InitVar[int] = 0
    display: InitVar[int] = 0
    vsync: InitVar[bool] = False

    surf: pg.Surface = field(init=False)

    def __post_init__(self, size, flags, depth, display, vsync) -> None:
        self.surf = pg.display.set_mode(size, flags, depth, display, vsync)

    @property
    def rect(self):
        return self.surf.get_rect()
    

@dataclass
class SpriteComponent(ecs.Component):
    """
    Pygame Sprite component, replacing pygame.sprite.Sprite.
    """
    surf: pg.Surface
    rect: pg.Rect = None
    area: pg.Rect = None
    _: KW_ONLY
    layer: int = 0
    flags: int = 0
    dirty: bool = True
    always_dirty: bool = True
    is_visible: bool = True

    pos_at: str = 'center'
    pos: InitVar[Optional[Vec2d | tuple[int, int]]] = None

    def __init_entity__(self, pos) -> None:
        if self.rect is None:
            self.rect = self.surf.get_rect()
        if self.area is None:
            self.area = self.surf.get_rect()
        if pos is None:
            pos = getattr(self.rect, self.pos_at)
        setattr(self.rect, self.pos_at, pos)

    def is_dirty(self) -> bool:
        """
        A sprite is dirty if it needs to update its rendered image.
        The dirty flag is unset once it is read this way to say that it has updated and
        does not need to be drawn.
        If the always_dirty flag is set, the dirty flag is ignored and the image of this
        sprite will always be updated.
        """
        if self.always_dirty:
            return True
        dirty, self.dirty = self.dirty, False
        return dirty

    def get_dirty(self) -> bool:
        """
        Returns the same value as sprite.is_dirty(), but with no side effects.
        """
        return self.always_dirty or self.dirty


@dataclass
class SpriteGroup(ecs.System):
    """
    System that groups all SpriteComponents of a given subclass and draws them as one batch.
    """
    sprite_cls: type = SpriteComponent

    def has_collision_with(
        self, scene: ecs.Scene, sprite: SpriteComponent,
        rect_getter: Callable[[SpriteComponent], pg.Rect] = attrgetter('rect')
        ) -> bool:
        """
        Returns True if the given SpriteComponent collides with any of the SpriteComponents in this
        SpriteGroup using the given Rect attributes, and False otherwise.
        The rect_getter parameter is a function that returns the desired Rect attribute, defaulting
        to 'rect'.
        """
        rect = rect_getter(sprite)
        for _, (s,) in scene.get_entities_with(self.sprite_cls):
            if rect.colliderect(rect_getter(s)):
                return True
        return False

    def get_collisions_with(
        self, scene: ecs.Scene, sprite: SpriteComponent,
        rect_getter: Callable[[SpriteComponent], pg.Rect] = attrgetter('rect')
        ) -> Generator[SpriteComponent, None, None]:
        """
        Returns a generator yielding all SpriteComponents in this group that collide with the given
        SpriteComponent using the given Rect attributes.
        The rect_getter parameter is a function that returns the desired Rect attribute, defaulting
        to 'rect'.
        """
        rect = rect_getter(sprite)
        for _, (s,) in scene.get_entities_with(self.sprite_cls):
            if rect.colliderect(rect_getter(s)):
                yield s

    def update(self, scene: ecs.Scene, dt: int) -> None:
        """
        Renders all SpriteComponents in this SpriteGroup to the WindowComponent.
        """
        window = scene.get_window()
        blitter = window.surf.blit

        rect_list = []
        for _, (sprite,) in scene.get_entities_with(self.sprite_cls):
            if not sprite.is_visible or not sprite.rect.colliderect(window.rect):
                continue
            blitter(sprite.surf, sprite.rect, sprite.area, sprite.flags)
            if sprite.is_dirty():
                rect_list.append(sprite.rect)

        scene.update_rects(rect_list)


@dataclass
class SortedGroup(SpriteGroup):
    """
    SpriteGroup that orders the SpriteComponents by some arbitrary key.
    """
    key: Callable[[SpriteComponent], Any] = attrgetter('layer')

    def update(self, scene: ecs.Scene, dt: int) -> None:
        """
        Renders all SpriteComponents in this IndexedGroup to the WindowComponent, ordered by
        the key function attribute.
        """
        window = scene.get_window()
        blitter = window.surf.blit
        sprites = sorted(
            (   
                sprite
                for _, (sprite,) in scene.get_entities_with(self.sprite_cls)
                if sprite.is_visible # and sprite.rect.colliderect(window.rect)
                ),
            key=self.key,
            )

        rect_list = []
        for sprite in sprites:
            blitter(sprite.surf, sprite.rect, sprite.area, sprite.flags)
            if sprite.is_dirty():
                rect_list.append(sprite.rect)

        scene.update_rects(rect_list)


Frame = TypedDict('Frame', index=tuple[int, int], duration=int)
FrameData = TypedDict('FrameData', loop=bool, frames=list[Frame, ...])

@dataclass
class AnimationComponent(ecs.Component):
    """
    Pygame Sprite animation component.
    """
    anim_size:  InitVar[tuple[int, int]]
    anim_data: dict[str, FrameData]
    curr_anim: str = None
    sprite_cls: type = SpriteComponent  

    index:    int = field(default=0, init=False)
    duration: int = field(default=0, init=False)
    loop:    bool = field(default=False, init=False)

    def __init_entity__(self, anim_size) -> None:
        self.anim_data = deepcopy(self.anim_data)
        for name, anim in self.anim_data.items():
            for frame in anim['frames']:
                frame['index'] = Vec2d(*frame['index']).elementwise() * anim_size

        if self.curr_anim is None:
            self.curr_anim = next(iter(self.anim_data))

        sprite = self.scene.get_component(self.entity, self.sprite_cls)
        sprite.area.topleft = self.get_pos()
        sprite.area.size = anim_size

    def __len__(self) -> int:
        return len(self.anim_data[self.curr_anim]['frames'])

    def __getitem__(self, item: str) -> tuple[tuple[int, int], int]:
        return self.anim_data[self.curr_anim]['frames'][item]

    def get_pos(self) -> Vec2d:
        """
        Sets the animation data for the current frame, then returns the index to
        the atlas position.
        Note that this will reset the current frame's timer, so it is not recommended
        to call this method other than when the animation state changes.
        """
        anim = self.anim_data[self.curr_anim]
        frame = anim['frames'][self.index]

        self.loop = anim['loop']
        self.duration = frame['duration']
        return frame['index']


@dataclass
class AnimationSystem(ecs.System):
    """
    System that handles the updating of animation states for Animations and Sprites.
    """
    sprite_cls: type = SpriteComponent

    def update(self, scene: ecs.Scene, dt: int) -> None:
        """
        Update the animation state of all AnimationComponents and the SpriteComponents associated
        with them.
        """
        for _, (sprite, anim) in scene.get_entities_with(self.sprite_cls, AnimationComponent):
            if anim.duration > 0:
                anim.duration -= 1
                continue
            if anim.loop or anim.index < len(anim) - 1:
                anim.index = (anim.index + 1) % len(anim)
                anim.dirty = True
            else:
                anim.index = min(anim.index, len(anim) - 1)
            sprite.area.topleft = anim.get_pos()


@dataclass
class PygameScene(ecs.Scene):
    """
    Scene object that manages the ECS for Pygame objects.
    """
    window: WindowComponent
    is_opengl: bool = False
    doublebuf: bool = False

    _rects: list[Iterable[pg.Rect]] = field(default_factory=list, init=None)

    def __post_init__(self) -> None:
        super().__init__()
        self.create_entity(self.window)
        self.bg_color = None

    def get_window(self) -> WindowComponent:
        return self.window

    def update_rects(self, rects: Iterable[pg.Rect]) -> None:
        if not (self.is_opengl or self.doublebuf):
            self._rects.extend(rects)

    def update(self, dt: int) -> None:
        """
        Handles updating all Systems in this Scene, 
        """
        if self.bg_color is not None:
            self.window.surf.fill(self.bg_color)
        super().update(dt)
        if self.is_opengl or self.doublebuf:
            pg.display.flip()
        else:
            pg.display.update(self._rects)
        self._rects.clear()


class PygameGame(object):
    """
    """
    def __init__(self, fps: int = 60) -> None:
        pg.init()
        self.fps = fps
        self.clock = pg.time.Clock()
        self.curr_fps = 0.

    def set_scene(self, scene: PygameScene) -> None:
        self.scene = scene

    def run(self) -> None:
        """
        Runs the game application.
        """
        while True:
            self.curr_fps = self.clock.get_fps()
            self.scene.update(self.clock.tick(self.fps))
