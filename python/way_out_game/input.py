"""Pure mappings from pygame controls to game actions."""

from __future__ import annotations

from types import MappingProxyType

import pygame

from .model import Action

_KEY_ACTIONS = MappingProxyType(
    {
        pygame.K_UP: Action.FORWARD,
        pygame.K_w: Action.FORWARD,
        pygame.K_DOWN: Action.BACKWARD,
        pygame.K_s: Action.BACKWARD,
        pygame.K_LEFT: Action.TURN_LEFT,
        pygame.K_a: Action.TURN_LEFT,
        pygame.K_RIGHT: Action.TURN_RIGHT,
        pygame.K_d: Action.TURN_RIGHT,
    }
)
_DEADZONE = 0.55
TURN_REPEAT_SECONDS = 0.5


def action_for_key(key: int) -> Action | None:
    """Translate a cursor or WASD key into an action."""

    return _KEY_ACTIONS.get(key)


def action_for_axes(x_axis: float, y_axis: float) -> Action | None:
    """Translate a gamepad stick or hat position into an action."""

    if max(abs(x_axis), abs(y_axis)) <= _DEADZONE:
        return None
    if abs(y_axis) >= abs(x_axis):
        return Action.FORWARD if y_axis < 0 else Action.BACKWARD
    return Action.TURN_LEFT if x_axis < 0 else Action.TURN_RIGHT
