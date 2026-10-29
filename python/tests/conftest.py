"""Shared fixtures for the game test suite."""

from unittest.mock import Mock

import pygame
import pytest

from way_out_game.model import Maze


@pytest.fixture
def gamepad_device() -> Mock:
    """Provide an opened PS4-style device with a non-index instance ID."""

    device = Mock(spec=pygame.joystick.JoystickType)
    device.get_instance_id.return_value = 42
    device.get_name.return_value = "PS4 Controller"
    device.get_numaxes.return_value = 6
    device.get_axis.side_effect = [0.0, 0.0, 0.0, 0.0, -1.0, -1.0].__getitem__
    device.get_numbuttons.return_value = 16
    device.get_button.return_value = False
    device.get_numhats.return_value = 0
    return device


@pytest.fixture
def maze() -> Maze:
    """Provide a deterministic maze for gameplay tests."""

    return Maze(
        rows=(
            "###############",
            "#.....#.......#",
            "#.###.#.#####.#",
            "#...#.#.....#.#",
            "###.#.###.#.#.#",
            "#...#.....#.#.#",
            "#.#######.#.#.#",
            "#.............#",
            "#.###########.#",
            "#............E#",
            "###############",
        ),
        exit_position=(13, 9),
    )
