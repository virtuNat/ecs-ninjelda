"""Entity Component System boilerplate module."""
from __future__ import annotations

from uuid import uuid4 as new_id
from operator import itemgetter
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from itertools import chain
from collections import defaultdict
from bisect import insort
from typing import Any, Optional, Iterable, Iterator, Generator

from .errors import MissingEntity, MissingComponent, MissingSystem


class EntityDict(dict):
    """Dict subclass for Entities to allow for more useful error messages."""

    def __getitem__(self, item: Entity) -> dict[type, Component]:
        if item in self:
            return super().__getitem__(item)
        raise MissingEntity(f'Entity with ID {item} is invalid')


class Singleton(ABCMeta):
    """
    Metaclass for enabling the creation of Singleton classes.
    ECS objects are not Singleton by default, and what Components and Systems will be designated
    as Singleton is up to the user's discretion.
    """
    _instances: dict[type, Any] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class Entity(int):
    """Integer alias used to ID a collection of Components."""

    def __new__(cls) -> Entity:
        return super().__new__(cls, new_id().int)


class Component(object):
    """Units of mutable data collected together and manipulated by Systems."""
    scene: Scene
    entity: Entity
    _args: tuple[Any, ...]
    _kwargs: dict[str, Any]

    def __post_init__(self, *args: Any, **kwargs: Any) -> None:
        self._args = args
        self._kwargs = kwargs

    def init_entity(self, scene: Scene, entity: Entity) -> None:
        """"""
        self.scene = scene
        self.entity = entity

        if not hasattr(self, '_args'): self._args = ()
        if not hasattr(self, '_kwargs'): self._kwargs = {}
        self.__init_entity__(*self._args, **self._kwargs)
        del self._args
        del self._kwargs

    def __init_entity__(self, *args: Any, **kwargs: Any) -> None:
        """"""


class System(metaclass=Singleton):
    """Processing units of logic that operate on Components."""

    @abstractmethod
    def update(self, scene: Scene, *args: Any, **kwargs: Any) -> None:
        """
        Entry point for the System's logical functionality where Entities and Components are modified.
        Usually, the sole argument is the delta time since the last call.
        """
        raise NotImplementedError('Subclasses of ecs.System must implement the update() method')


class Scene(object):
    """Collections of Entities and Systems upon which game logic is handled."""
    _entities: dict[Entity, dict[type, Component]]
    _components: defaultdict[type, set[Entity]]

    _systems: list[tuple[int, dict[type, System]], ...]
    _priorities: set[int, ...]

    def __init__(self) -> None:
        self._entities = EntityDict()
        self._components = defaultdict(set)
        self._systems = []
        self._priorities = set()

    def create_entity(self, *components: Component) -> Entity:
        """
        Generates a new Entity instance with the specified optional Components.
        """
        entity = Entity()
        self._entities[entity] = comp_dict = {}
        for component in components:
            comp_dict[type(component)] = component
            self._components[type(component)].add(entity)
            component.init_entity(self, entity)
        return entity

    def get_entities(self) -> Iterator[Entity]:
        """
        Returns an iterator for the list of all Entities in the Scene.
        """
        return iter(self._entities)

    def get_entities_with(self, *comp_classes: type) -> Generator[tuple[Entity, tuple[Component, ...]], None, None]:
        """
        Returns a generator for (Entity, (Components)) tuples
        for all Entities that posses the specified Components.
        """
        if not comp_classes:
            return
        entities = set.intersection(*map(self._components.__getitem__, comp_classes))
        for entity, entity_dict in self._entities.items():
            if entity not in entities: continue
            yield entity, (entity_dict[comp_cls] for comp_cls in comp_classes)

    def del_entity(self, entity: Entity) -> None:
        """
        Deletes a given Entity instance and all associated Components.
        """
        for comp_cls in self._entities[entity]:
            self._components[comp_cls].remove(entity)
        del self._entities[entity]

    def add_component(self, entity: Entity, component: Component) -> None:
        """
        Adds the given Component to the target Entity.
        """
        self._entities[entity][type(component)] = component
        self._components[type(component)].add(entity)
        component.init_entity(self, entity)

    def add_components(self, entity: Entity, *components: Component) -> None:
        """
        Adds the given Components to the target Entity.
        """
        for component in components:
            self._entities[entity][type(component)] = component
            self._components[type(component)].add(entity)
            component.init_entity(self, entity)

    def get_components_from(self, entities: Iterable[Entity, ...], comp_cls: type) -> Generator[Component, None, None]:
        """
        Returns a generator for the Components of the given type in the same order as the
        iterable of Entities provided.
        """
        for entity in entities:
            comp_dict = self._entities[entity]
            if comp_cls not in comp_dict:
                raise MissingComponent(
                f'Entity with ID {entity} does not have Component "{comp_cls.__name__}"'
                )
            yield comp_dict[comp_cls]

    def has_component(self, entity: Entity, comp_cls: type) -> bool:
        """
        Returns True if the specified Entity has a Component of that type, and False otherwise.
        """
        return comp_cls in self._entities[entity]

    def has_components(self, entity: Entity, *comp_classes: type) -> bool:
        """
        Returns True if the specified Entity has a Component of all given types, and False otherwise.
        """
        entity_sets = [self._components[comp_cls] for comp_cls in comp_classes]
        entities = set.intersection(*entity_sets) if entity_sets else set()
        return entity in entities

    def get_single_component(self, comp_cls: type) -> Component:
        """
        Returns one arbitrary Component of that class. Useful for single-instance Components.
        """
        return self._entities[next(iter(self._components[comp_cls]))][comp_cls]

    def get_component(self, entity: Entity, comp_cls: type) -> Component:
        """
        Returns the Component of the given type if the Entity has it, otherwise throws an exception.
        """
        if comp_cls not in (comp_dict := self._entities[entity]):
            raise MissingComponent(
                f'Entity with ID {entity} does not have Component "{comp_cls.__name__}"'
                )
        return comp_dict[comp_cls]

    def get_components(self, entity: Entity, *comp_classes: type) -> list[Component]:
        """
        Returns the Components of the given types if the Entity has these, otherwise throws an exception.
        """
        comp_dict = self._entities[entity]
        components = []
        for comp_cls in comp_classes:
            if comp_cls not in comp_dict:
                raise MissingComponent(
                    f'Entity with ID {entity} does not have Component "{comp_cls.__name__}"'
                    )
            components.append(comp_dict[comp_cls])
        return components

    def try_component(self, entity: Entity, comp_cls: type) -> Optional[Component]:
        """
        Returns the Component of the given type if the Entity has it, and None otherwise.
        This allows the usage of the walrus operator to make code more concise.
        """
        try:
            return self._entities[entity][comp_cls]
        except KeyError:
            return None

    def try_components(self, entity: Entity, *comp_classes: type) -> list[Optional[Component]]:
        """
        Returns the Components of the given types if the Entity has these, and None otherwise.
        This allows the usage of the walrus operator to make code more concise.
        """
        comp_dict = self._entities[entity]
        return [
            comp_dict[comp_cls] if comp_cls in comp_dict else None
            for comp_cls in comp_classes
            ]

    def del_component(self, entity: Entity, comp_cls: type) -> None:
        """
        Deletes the Component of the given type from the Entity.
        Throws an exception if the Component does not exist.
        """
        if comp_cls not in self._entities[entity]:
            raise MissingComponent(
                f'Entity with ID {entity} does not have Component "{comp_cls.__name__}"'
                )
        component = self._entities[entity].pop(comp_cls)
        self._components[comp_cls].remove(entity)
        component.entity = None

    def add_system(self, system: System, priority: int = 0) -> None:
        """
        Adds a System to to this Scene with an optional priority value.
        Systems with higher priorities go first, and Systems of the same priority go in an arbitrary order.
        """
        if priority not in self._priorities:
            self._priorities.add(priority)
            insort(self._systems, (priority, {type(system): system}), key=itemgetter(0))
        else:
            system_dict = next(sys for prio, sys in self._systems if prio == priority)
            system_dict[type(system)] = system

    def add_systems(self, systems: tuple[System] | tuple[System, int]) -> None:
        for args in systems:
            if len(args) > 1:
                system, priority = args
            else:
                system = args[0]
            if priority not in self._priorities:
                self._priorities.add(priority)
                insort(self._systems, (priority, {type(system): system}), key=itemgetter(0))
            else:
                system_dict = next(sys for prio, sys in self._systems if prio == priority)
                system_dict[type(system)] = system

    def del_system(self, system_cls: type) -> None:
        """
        Removes the System of the given type from this Scene.
        Useful if a transition needs to occur without needing to start from scratch.
        """
        for priority, systems in self._systems:
            if system_cls in systems:
                break
        else:
            raise MissingSystem(f'System "{system_cls.__name__}" is not present in this Scene.')
        del self._systems[priority][1][system_cls]

    def update(self, *args: Any, **kwargs: Any) -> None:
        """
        Runs the update method on all Systems present in this Scene.
        """
        for system in chain.from_iterable(systems[1].values() for systems in reversed(self._systems)):
            system.update(self, *args, **kwargs)
