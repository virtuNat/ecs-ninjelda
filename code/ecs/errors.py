"""Errors module."""

class ECSError(Exception):
    """Entity Component System Exceptions superclass."""


class MissingEntity(ECSError):
    """Raised when attempting to use an Entity ID not present in a Scene."""


class MissingComponent(ECSError):
    """Raised when attempting to obtain a Component not present in an Entity."""


class MissingSystem(ECSError):
    """Raised when attempting to access a System not present in a Scene."""
