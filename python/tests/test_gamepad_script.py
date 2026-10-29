"""Headless tests for the standalone gamepad visualizer."""

from collections.abc import Generator
from unittest.mock import Mock

import pygame
import pytest

from script import gamepad_test as visualizer


@pytest.fixture(autouse=True)
def pygame_init(monkeypatch: pytest.MonkeyPatch) -> Generator[None]:
    """Keep these tests independent of physical displays and controllers."""

    def no_events() -> list[pygame.event.Event]:
        return []

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    monkeypatch.setattr(pygame.joystick, "get_count", lambda: 0)
    monkeypatch.setattr(pygame.event, "get", no_events)
    yield
    pygame.quit()


def make_joystick(instance_id: int = 42) -> Mock:
    """Create a device whose index differs from its instance ID."""

    joystick = Mock(spec=pygame.joystick.JoystickType)
    joystick.get_instance_id.return_value = instance_id
    joystick.get_name.return_value = "Test gamepad"
    joystick.get_numaxes.return_value = 6

    def axis_value(index: int) -> float:
        return [0.0, 0.0, 0.0, 0.0, -1.0, -1.0][index]

    def button_value(index: int) -> bool:
        return index == 0

    joystick.get_axis.side_effect = axis_value
    joystick.get_numbuttons.return_value = 12
    joystick.get_button.side_effect = button_value
    joystick.get_numhats.return_value = 1
    joystick.get_hat.return_value = (1, -1)
    return joystick


def test_snapshot_reads_every_control() -> None:
    """FR-VIZ-001
    Feature: Gamepad state inspection
    Scenario: A snapshot reads every raw control
    GIVEN a gamepad with axes, buttons, and a diagonal hat state
    WHEN a snapshot is read
    THEN all controls are captured and absent indices use safe defaults
    """

    state = visualizer.GamepadState.read(make_joystick())
    assert state.name == "Test gamepad"
    assert state.axes == [0, 0, 0, 0, -1, -1]
    assert state.buttons == [True] + [False] * 11
    assert state.hats == [(1, -1)]
    assert state.axis(8) == 0
    assert not state.pressed(20)


@pytest.mark.parametrize(
    "control, point",
    [
        ("button", (495, 267)),
        ("stick", (257, 280)),
        ("stick_button", (235, 280)),
        ("trigger", (120, 90)),
        ("hat_right", (166, 229)),
        ("hat_up", (144, 206)),
        ("extra_button", (26 + 11 * 48, 467)),
        ("extra_axis", (972, 116 + 6 * 30 + 11)),
    ],
)
def test_controls_highlight_and_release(
    control: str, point: tuple[int, int]
) -> None:
    """FR-VIZ-002
    Feature: Gamepad visualizer controls
    Scenario: Active controls highlight and released controls reset
    GIVEN an illustrated button, stick, trigger, hat, or extra control
    WHEN its state changes from idle to active and back
    THEN the corresponding rendered pixel highlights and returns to idle
    """

    surface = pygame.Surface((visualizer.WIDTH, 620))
    font = pygame.font.Font(None, 24)
    rest = [0.0] * 4 + [-1.0, -1.0, 0.0]
    state = visualizer.GamepadState(
        "Test", rest.copy(), [False] * 12, [(0, 0)]
    )
    visualizer.draw_gamepad(surface, font, state, rest)
    idle_pixel = surface.get_at(point)
    if control == "button":
        state.buttons[0] = True
    elif control == "stick":
        state.axes[0] = 1.0
    elif control == "stick_button":
        state.buttons[7] = True
    elif control == "trigger":
        state.axes[4] = 1.0
    elif control.startswith("hat"):
        state.hats[0] = (1, 1)
    elif control == "extra_button":
        state.buttons[11] = True
    else:
        state.axes[6] = 1.0
    visualizer.draw_gamepad(surface, font, state, rest)
    assert surface.get_at(point)[:3] == visualizer.ACTIVE
    state.axes = rest.copy()
    state.buttons = [False] * 12
    state.hats = [(0, 0)]
    visualizer.draw_gamepad(surface, font, state, rest)
    assert surface.get_at(point) == idle_pixel


@pytest.mark.parametrize("button", [0, 1, 2, 3, 5, 4, 6, 7, 8, 9, 10, 15])
def test_remapped_silhouette_buttons(button: int) -> None:
    """FR-VIZ-002
    Feature: Gamepad visualizer controls
    Scenario: Raw buttons use their documented silhouette mappings
    GIVEN a supported raw button index
    WHEN that button is pressed and released
    THEN only its mapped silhouette and raw readout highlight
    """

    surface = pygame.Surface((visualizer.WIDTH, 620))
    font = pygame.font.Font(None, 24)
    state = visualizer.GamepadState("Test", [], [False] * 16, [])
    controls: dict[int, tuple[int, int]] = {
        0: (495, 267),
        1: (530, 232),
        2: (460, 232),
        3: (495, 197),
        9: (150, 110),
        10: (490, 110),
        7: (235, 280),
        8: (405, 280),
        4: (200, 130),
        6: (440, 130),
        15: (320, 150),
        5: (320, 265),
    }
    raw_point = (26 + button * 48, 467)
    points: list[tuple[int, int]] = [*controls.values(), raw_point]
    visualizer.draw_gamepad(surface, font, state, [])
    idle_pixels = [surface.get_at(point) for point in points]

    state.buttons[button] = True
    visualizer.draw_gamepad(surface, font, state, [])
    assert surface.get_at(raw_point)[:3] == visualizer.ACTIVE
    for mapped_button, point in controls.items():
        assert (surface.get_at(point)[:3] == visualizer.ACTIVE) == (
            mapped_button == button
        )

    state.buttons[button] = False
    visualizer.draw_gamepad(surface, font, state, [])
    assert [surface.get_at(point) for point in points] == idle_pixels


@pytest.mark.parametrize("pressed", [False, True])
def test_upper_middle_button_is_wide_rectangle(pressed: bool) -> None:
    """FR-VIZ-002
    Feature: Gamepad visualizer controls
    Scenario: The upper middle button has a stable rectangular shape
    GIVEN button B15 in either idle or pressed state
    WHEN the silhouette is drawn
    THEN its bounds remain rectangular and distinct from the controller body
    """

    surface = pygame.Surface((visualizer.WIDTH, 620))
    state = visualizer.GamepadState("Test", [], [False] * 16, [])
    state.buttons[15] = pressed
    visualizer.draw_gamepad(surface, pygame.font.Font(None, 24), state, [])
    color = visualizer.ACTIVE if pressed else visualizer.IDLE
    for point in ((230, 120), (409, 120), (230, 209), (409, 209)):
        assert surface.get_at(point)[:3] == color
    for point in ((229, 165), (410, 165), (320, 119), (320, 210)):
        assert surface.get_at(point)[:3] == visualizer.BODY


@pytest.mark.parametrize("hats", [[], [(0, 0)], [(1, 0)]])
@pytest.mark.parametrize("button", [11, 12, 13, 14])
def test_dpad_button_highlights_both_views(
    hats: list[tuple[int, int]],
    button: int,
) -> None:
    """FR-VIZ-002
    Feature: Gamepad visualizer controls
    Scenario: D-pad buttons highlight both representations
    GIVEN a D-pad button with any supported hat state
    WHEN the button is pressed and released
    THEN its silhouette direction and raw button readout update together
    """

    surface = pygame.Surface((visualizer.WIDTH, 620))
    font = pygame.font.Font(None, 24)
    state = visualizer.GamepadState("Test", [], [False] * 15, hats)
    directions = {
        11: (144, 206),
        12: (144, 252),
        13: (121, 229),
        14: (167, 229),
    }
    points = (directions[button], (26 + button * 48, 467))
    visualizer.draw_gamepad(surface, font, state, [])
    idle_pixels = [surface.get_at(point) for point in points]
    other_pixels = {
        point: surface.get_at(point)
        for other_button, point in directions.items()
        if other_button != button
    }

    state.buttons[button] = True
    visualizer.draw_gamepad(surface, font, state, [])
    for point in points:
        assert surface.get_at(point)[:3] == visualizer.ACTIVE
    for point, color in other_pixels.items():
        assert surface.get_at(point) == color

    state.buttons[button] = False
    visualizer.draw_gamepad(surface, font, state, [])
    assert [surface.get_at(point) for point in points] == idle_pixels


def test_empty_device_renders() -> None:
    """FR-VIZ-002
    Feature: Gamepad visualizer controls
    Scenario: A device with no controls renders safely
    GIVEN a gamepad snapshot with no axes, buttons, or hats
    WHEN the visualizer draws it
    THEN the controller surface renders without indexing errors
    """

    surface = pygame.Surface((visualizer.WIDTH, 620))
    visualizer.draw_gamepad(
        surface,
        pygame.font.Font(None, 24),
        visualizer.GamepadState("Empty", [], [], []),
        [],
    )
    assert surface.get_at((320, 250))[:3] == visualizer.BODY


def test_no_gamepad_loop() -> None:
    """FR-VIZ-003
    Feature: Gamepad visualizer lifecycle
    Scenario: The visualizer runs while no gamepad is connected
    GIVEN no connected gamepad
    WHEN the visualizer runs for bounded frames
    THEN it remains operational and pygame is released on exit
    """

    visualizer.run_gamepad_test(max_frames=2)
    assert not pygame.get_init()


@pytest.mark.parametrize(
    "event",
    [
        pygame.event.Event(pygame.QUIT),
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE),
    ],
)
def test_exit_events(
    event: pygame.event.Event, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-VIZ-003
    Feature: Gamepad visualizer lifecycle
    Scenario: Window close and Escape exit the visualizer
    GIVEN either a window quit event or Escape key press
    WHEN the visualizer processes the event
    THEN it exits and releases pygame
    """

    def queued_event() -> list[pygame.event.Event]:
        return [event]

    monkeypatch.setattr(pygame.event, "get", queued_event)
    visualizer.run_gamepad_test(max_frames=2)
    assert not pygame.get_init()


def test_hotplug_switch_and_disconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-VIZ-003
    Feature: Gamepad visualizer lifecycle
    Scenario: Hot-plugging, switching, and removal preserve device identity
    GIVEN two gamepads that connect and disconnect while the window is open
    WHEN Tab switches the selected device and one device is removed
    THEN the remaining device is usable and both devices are released
    """

    first, second = make_joystick(42), make_joystick(99)
    monkeypatch.setattr(
        pygame.joystick, "Joystick", [first, second].__getitem__
    )
    events = iter(
        [
            [pygame.event.Event(pygame.JOYDEVICEADDED, device_index=0)],
            [
                pygame.event.Event(pygame.JOYDEVICEADDED, device_index=1),
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB),
            ],
            [pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=99)],
            [pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=42)],
        ]
    )
    monkeypatch.setattr(pygame.event, "get", lambda: next(events))
    seen: list[list[bool]] = []

    def second_button_pressed(index: int) -> bool:
        return index == 1

    def record_draw(
        _screen: pygame.Surface,
        _font: pygame.font.Font,
        state: visualizer.GamepadState,
        _rest: list[float],
    ) -> None:
        seen.append(state.buttons)

    second.get_button.side_effect = second_button_pressed
    monkeypatch.setattr(
        visualizer,
        "draw_gamepad",
        record_draw,
    )
    visualizer.run_gamepad_test(max_frames=4)
    assert [buttons[:2] for buttons in seen] == [
        [True, False],
        [False, True],
        [True, False],
    ]
    first.quit.assert_called_once()
    second.quit.assert_called_once()
    assert not pygame.get_init()


def test_startup_device_and_duplicate_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-VIZ-003
    Feature: Gamepad visualizer lifecycle
    Scenario: Startup enumeration tolerates a duplicate add event
    GIVEN a gamepad connected before startup and its added notification
    WHEN the visualizer initializes
    THEN the device is registered and released only once
    """

    joystick = make_joystick()
    monkeypatch.setattr(pygame.joystick, "get_count", lambda: 1)

    def open_startup_device(_index: int) -> Mock:
        return joystick

    monkeypatch.setattr(pygame.joystick, "Joystick", open_startup_device)
    monkeypatch.setattr(
        pygame.event,
        "get",
        lambda: [pygame.event.Event(pygame.JOYDEVICEADDED, device_index=0)],
    )
    visualizer.run_gamepad_test(max_frames=1)
    joystick.quit.assert_called_once()


def test_large_device_expands_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-VIZ-004
    Feature: Gamepad visualizer sizing
    Scenario: The window expands for devices with many controls
    GIVEN a device with more axes, buttons, and hats than the base layout
    WHEN the visualizer draws its controls
    THEN the window grows to contain the expanded readouts
    """

    joystick = make_joystick()
    joystick.get_numaxes.return_value = 16

    def centered_axis(_index: int) -> float:
        return 0.0

    joystick.get_axis.side_effect = centered_axis
    joystick.get_numbuttons.return_value = 64
    joystick.get_numhats.return_value = 4
    monkeypatch.setattr(pygame.joystick, "get_count", lambda: 1)

    def open_large_device(_index: int) -> Mock:
        return joystick

    monkeypatch.setattr(pygame.joystick, "Joystick", open_large_device)
    sizes: list[tuple[int, int]] = []
    draw = visualizer.draw_gamepad

    def record_draw(
        screen: pygame.Surface,
        font: pygame.font.Font,
        state: visualizer.GamepadState,
        rest: list[float],
    ) -> None:
        sizes.append(screen.get_size())
        draw(screen, font, state, rest)

    monkeypatch.setattr(visualizer, "draw_gamepad", record_draw)
    visualizer.run_gamepad_test(max_frames=1)
    assert sizes == [(1000, 932)]


def test_cleanup_after_render_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-VIZ-001
    Feature: Visualizer resource cleanup
    Scenario: Rendering failures still release resources
    GIVEN an open gamepad and a renderer that raises an error
    WHEN the visualizer exits exceptionally
    THEN the error propagates and both the device and pygame are closed
    """

    joystick = make_joystick()
    monkeypatch.setattr(pygame.joystick, "get_count", lambda: 1)

    def open_failing_device(_index: int) -> Mock:
        return joystick

    monkeypatch.setattr(pygame.joystick, "Joystick", open_failing_device)
    monkeypatch.setattr(
        visualizer,
        "draw_gamepad",
        Mock(side_effect=RuntimeError("draw failed")),
    )
    with pytest.raises(RuntimeError, match="draw failed"):
        visualizer.run_gamepad_test(max_frames=1)
    joystick.quit.assert_called_once()
    assert not pygame.get_init()
