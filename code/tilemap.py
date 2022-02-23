# Tilemap stuff.
import types
from collections import defaultdict
from dataclasses import InitVar, dataclass, field
from typing import Any, Optional, Callable

import pygame as pg
from pygame.math import Vector2 as Vec2d
import pytmx
from pytmx.util_pygame import load_pygame

import ecs
from ecs.pygame import SpriteComponent
from support import Hitbox, OffsetComponent
from settings import ASSET_PATHS, DISPLAY
from player import create_player

_name: str = ''
_tilemaps: dict[str, pytmx.TiledMap] = {}
_curr_map: list[ecs.Entity] = []
_destructibles: set[ecs.Entity] = set()
_actors: dict[int, list[tuple[int, int], ...]] = defaultdict(list)

def get_current_map() -> pytmx.TiledMap:
    return _tilemaps[_name]

def load_map(scene: ecs.Scene, map_name: str) -> None:
    # Check if map is already loaded.
    try:
        tile_map = _tilemaps[map_name]
    except KeyError:
        tile_map = load_pygame(ASSET_PATHS.asset_path/'maps'/f'{map_name}.tmx')
        _tilemaps[map_name] = tile_map
        _name = map_name
    # Clear all previous map data.
    if _curr_map:
        for eid in _curr_map:
            scene.del_entity(eid)
        _curr_map.clear()
        for eid in _destructibles:
            scene.del_entity(eid)
        _destructibles.clear()
        _actors.clear()
    # Tile size for all non-object tiles.
    tile_size = DISPLAY.scaling * Vec2d(
        tile_map.tilewidth,
        tile_map.tileheight,
        )
    # Layer size for all tilemap terrain layers.
    layer_size = tile_size.elementwise() * (tile_map.width, tile_map.height)
    for idx, ldx in enumerate(tile_map.visible_tile_layers):
        layer = tile_map.layers[ldx]
        if not layer.name or not layer.name.startswith('terrain'):
            continue
        tile_map_layer = SpriteComponent(
            pg.Surface(layer_size, pg.SRCALPHA),
            layer=idx,
            pos_at='topleft',
            always_dirty=False,
            )
        _curr_map.append(scene.create_entity(
            tile_map_layer, OffsetComponent()
            ))
        for x, y, surf in layer.tiles():
            tile_map_layer.surf.blit(
                pg.transform.scale(surf, tile_size),
                tile_size.elementwise() * (x, y)
                )
    # Create static background color from terrain map topleft pixel to avoid scrolling artifacts.
    scene.bg_color = scene.get_component(_curr_map[0], SpriteComponent).surf.get_at((0, 0))
    # Add invisible impassable tiles.
    for x, y, surf in tile_map.get_layer_by_name('impassable').tiles():
        _curr_map.append(scene.create_entity(
            Hitbox(
                pg.Rect(tile_size.elementwise() * (x, y), tile_size).inflate(0, -12)
                ),
            OffsetComponent(),
            ))
    # Populate actor initial position dictionary.
    for x, y, gid in tile_map.get_layer_by_name('actors'):
        if gid:
            _actors[gid].append((x, y))
    # Populate destructible terrain objects.
    for x, y, surf in tile_map.get_layer_by_name('destructible').tiles():
        _destructibles.add(scene.create_entity(
            SpriteComponent(
                pg.transform.scale(surf, tile_size),
                rect=pg.Rect(tile_size.elementwise() * (x, y), tile_size),
                layer=3,
                pos_at='topleft',
                always_dirty=False,
                ),
            OffsetComponent(),
            DestructibleComponent(),
            ))
    # Populate multi-tile terrain objects.
    for obj in tile_map.get_layer_by_name('objects'):
        
        obj_pos = Vec2d(obj.x, obj.y) * DISPLAY.scaling
        obj_size = Vec2d(obj.image.get_size()) * DISPLAY.scaling
        
        if 'colliders' in obj.properties:
            box = obj.colliders[0]
            box_pos = Vec2d(box.x, box.y) * DISPLAY.scaling
            box_size = Vec2d(box.width, box.height) * DISPLAY.scaling
        else:
            box_pos = obj_pos
            box_size = obj_size
        
        _curr_map.append(scene.create_entity(
            SpriteComponent(
                pg.transform.scale(obj.image, obj_size),
                pg.Rect(obj_pos, obj_size),
                layer=3,
                pos_at='topleft',
                always_dirty=False,
                ),
            OffsetComponent(),
            Hitbox(
                pg.Rect(obj_pos + box_pos, box_size),
                pos_at='topleft',
                pos_from=lambda s: s.rect.topleft,
                ),
            ))

def load_player_from(scene: ecs.Scene, map_name: str = _name) -> None:
    # Map should be loaded, and technically could be loaded from here...
    try:
        tile_map = _tilemaps[map_name]
    except KeyError:
        raise ValueError(f'Map "{map_name}" is not loaded')

    tile_size = DISPLAY.scaling * Vec2d(
        tile_map.tilewidth,
        tile_map.tileheight,
        )
    # Get player position using the legend layer to reference the actor id.
    legend = tile_map.get_layer_by_name('legend')
    player_pos = _actors[legend.data[0][0]][0]
    return create_player(scene, tile_size.elementwise() * player_pos)


class DestructibleComponent(ecs.Component):
    """Marks an entity as being destructible by the player."""
