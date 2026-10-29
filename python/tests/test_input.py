"""Tests for keyboard and gamepad action mappings."""

import pygame
import pytest

from way_out_game.input import action_for_axes, action_for_key
from way_out_game.model import Action


@pytest.mark.parametrize(
    "key, action",
    [
        (pygame.K_UP, Action.FORWARD),
        (pygame.K_w, Action.FORWARD),
        (pygame.K_DOWN, Action.BACKWARD),
        (pygame.K_s, Action.BACKWARD),
        (pygame.K_LEFT, Action.TURN_LEFT),
        (pygame.K_a, Action.TURN_LEFT),
        (pygame.K_RIGHT, Action.TURN_RIGHT),
        (pygame.K_d, Action.TURN_RIGHT),
    ],
)
def test_keyboard_actions(key: int, action: Action) -> None:
    """FR-INP-001
    Feature: Keyboard movement controls
    Scenario: Supported keys select their mapped action
    GIVEN a cursor or WASD movement key
    WHEN the key is translated
    THEN the matching action is returned
    """

    assert action_for_key(key) is action


def test_unknown_key_has_no_action() -> None:
    """FR-INP-001
    Feature: Keyboard movement controls
    Scenario: Unsupported keys are ignored
    GIVEN a key outside the movement controls
    WHEN the key is translated
    THEN no action is returned
    """

    assert action_for_key(pygame.K_ESCAPE) is None


@pytest.mark.parametrize(
    "axes, action",
    [
        ((0.0, -1.0), Action.FORWARD),
        ((0.0, 1.0), Action.BACKWARD),
        ((-1.0, 0.0), Action.TURN_LEFT),
        ((1.0, 0.0), Action.TURN_RIGHT),
        ((0.4, -0.8), Action.FORWARD),
    ],
)
def test_gamepad_axes(axes: tuple[float, float], action: Action) -> None:
    """FR-INP-002
    Feature: Analog and hat input
    Scenario: The dominant axis selects an action
    GIVEN normalized horizontal and vertical axes outside the deadzone
    WHEN the axes are translated
    THEN the dominant direction selects movement or turning
    """

    assert action_for_axes(*axes) is action


@pytest.mark.parametrize("axes", [(0.0, 0.0), (0.4, 0.4), (-0.55, 0.0)])
def test_gamepad_deadzone(axes: tuple[float, float]) -> None:
    """FR-INP-002
    Feature: Analog and hat input
    Scenario: Values at or inside the deadzone are ignored
    GIVEN axes whose greatest magnitude is at most 0.55
    WHEN the axes are translated
    THEN no action is returned
    """

    assert action_for_axes(*axes) is None


def test_vertical_axis_wins_equal_magnitude_tie() -> None:
    """FR-INP-002
    Feature: Analog and hat input
    Scenario: Vertical input wins a magnitude tie
    GIVEN horizontal and vertical axes with equal magnitude
    WHEN the axes are translated
    THEN the vertical movement action is returned
    """

    assert action_for_axes(0.8, -0.8) is Action.FORWARD
