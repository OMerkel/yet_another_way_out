"""Tests for the controller backend shared by the game and visualizer."""

from collections.abc import Generator
from unittest.mock import Mock

import pygame
import pytest

from way_out_game.gamepad import Gamepads


@pytest.fixture(autouse=True)
def pygame_init(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    """Pump events without a physical display or attached controllers."""

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    monkeypatch.setattr(pygame.joystick, "get_count", lambda: 0)
    yield
    pygame.quit()


def test_no_devices(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-PAD-001
    Feature: Optional gamepad support
    Scenario: The backend opens with no attached devices
    GIVEN no connected gamepads
    WHEN connected devices are opened and polled
    THEN the backend returns no sticks and opens no device
    """

    open_device = Mock()
    monkeypatch.setattr(pygame.joystick, "Joystick", open_device)
    gamepads = Gamepads()
    gamepads.open_connected()
    assert not gamepads.left_sticks()
    gamepads.close()
    open_device.assert_not_called()


def test_device_lifecycle(
    monkeypatch: pytest.MonkeyPatch, gamepad_device: Mock
) -> None:
    """FR-PAD-002
    Feature: Gamepad lifecycle
    Scenario: Devices are keyed by stable instance ID
    GIVEN an attached gamepad and a duplicate added notification
    WHEN the backend adds then removes the device
    THEN it registers once and clears device, axis, and stick state
    """

    def open_device(_index: int) -> Mock:
        return gamepad_device

    monkeypatch.setattr(pygame.joystick, "get_count", lambda: 1)
    monkeypatch.setattr(pygame.joystick, "Joystick", open_device)
    gamepads = Gamepads()
    gamepads.open_connected()
    gamepads.handle_event(
        pygame.event.Event(pygame.JOYDEVICEADDED, device_index=0)
    )
    assert gamepads.devices == {42: gamepad_device}
    assert gamepads.resting_axes == {42: [0.0, 0.0, 0.0, 0.0, -1.0, -1.0]}
    assert gamepads.left_sticks() == {42: [0.0, 0.0]}
    gamepads.handle_event(
        pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=42)
    )
    gamepads.handle_event(
        pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=42)
    )
    assert not gamepads.devices
    assert not gamepads.resting_axes
    assert not gamepads.left_sticks()
    gamepads.close()
    gamepad_device.quit.assert_called_once()


def test_device_with_fewer_axes(
    monkeypatch: pytest.MonkeyPatch, gamepad_device: Mock
) -> None:
    """FR-PAD-003
    Feature: Variable gamepad capabilities
    Scenario: Missing stick axes are centered
    GIVEN a device exposing fewer axes than the left stick requires
    WHEN the backend polls its stick
    THEN absent axes read as zero and repeated close is harmless
    """

    def open_device(_index: int) -> Mock:
        return gamepad_device

    monkeypatch.setattr(pygame.joystick, "Joystick", open_device)
    gamepad_device.get_numaxes.return_value = 1
    gamepad_device.get_axis.side_effect = None
    gamepad_device.get_axis.return_value = 0.8
    gamepads = Gamepads()
    gamepads.add_device(0)
    assert gamepads.left_sticks() == {42: [0.8, 0.0]}
    gamepads.close()
    assert not gamepads.devices
    assert not gamepads.resting_axes
    gamepads.close()
    gamepad_device.quit.assert_called_once()


def test_multiple_controllers_keep_independent_values(
    monkeypatch: pytest.MonkeyPatch, gamepad_device: Mock
) -> None:
    """FR-PAD-004
    Feature: Multiple gamepads
    Scenario: Controller state remains independent by instance ID
    GIVEN two connected gamepads with distinct IDs and axis values
    WHEN one device is removed
    THEN the other device retains its own values and remains open
    """

    second = Mock(spec=pygame.joystick.JoystickType)
    second.get_instance_id.return_value = 99
    second.get_name.return_value = "Second controller"
    second.get_numaxes.return_value = 2
    second.get_axis.side_effect = [-0.8, 0.9].__getitem__
    second.get_numbuttons.return_value = 0
    second.get_numhats.return_value = 0
    monkeypatch.setattr(pygame.joystick, "get_count", lambda: 2)
    monkeypatch.setattr(
        pygame.joystick, "Joystick", [gamepad_device, second].__getitem__
    )
    gamepads = Gamepads()
    gamepads.open_connected()
    assert gamepads.left_sticks() == {42: [0.0, 0.0], 99: [-0.8, 0.9]}
    gamepads.handle_event(
        pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=42)
    )
    assert gamepads.left_sticks() == {99: [-0.8, 0.9]}
    gamepads.close()
    gamepad_device.quit.assert_called_once()
    second.quit.assert_called_once()
