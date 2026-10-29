"""Tests for pygame loop composition and event handling."""

from dataclasses import replace
from unittest.mock import Mock

import pygame
import pytest

import way_out_game.app as game_app
from way_out_game.app import apply_held_axes, handle_event, run_game
from way_out_game.model import (
    ANIMATION_STEPS,
    SOLUTION_COUNTDOWN_DURATION,
    Action,
    Direction,
    GameState,
    Maze,
    advance_animation,
    begin_action,
    generate_maze,
    initial_state,
)


@pytest.fixture(name="connected_gamepad")
def connected_gamepad_fixture(
    monkeypatch: pytest.MonkeyPatch, gamepad_device: Mock, maze: Maze
) -> Mock:
    """Run the game with an opened device, without synthetic axis events."""

    def no_events() -> list[pygame.event.Event]:
        return []

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setattr(pygame.joystick, "get_count", lambda: 1)
    monkeypatch.setattr(
        pygame.joystick, "Joystick", Mock(return_value=gamepad_device)
    )
    monkeypatch.setattr(pygame.event, "get", no_events)
    corridor = replace(
        maze, entry_position=(3, 1), entry_facing=Direction.EAST
    )
    monkeypatch.setattr(game_app, "generate_maze", lambda: corridor)
    return gamepad_device


@pytest.fixture(name="scene")
def scene_fixture(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Capture game states without rendering a full maze in loop tests."""

    draw = Mock()
    monkeypatch.setattr(game_app, "draw_scene", draw)
    return draw


@pytest.mark.parametrize(
    "axes, action",
    [
        ((-1.0, 0.0), Action.TURN_LEFT),
        ((1.0, 0.0), Action.TURN_RIGHT),
        ((0.0, -1.0), Action.FORWARD),
        ((0.0, 1.0), Action.BACKWARD),
        ((0.0, 0.0), None),
        ((0.55, -0.55), None),
    ],
)
def test_run_game_opens_and_polls_left_stick(
    connected_gamepad: Mock,
    scene: Mock,
    axes: tuple[float, float],
    action: Action | None,
) -> None:
    """FR-APP-001
    Feature: Polled gamepad movement
    Scenario: Held left-stick input is read without motion events
    GIVEN an attached controller with its left stick already deflected
    WHEN the game loop polls one frame
    THEN the matching action begins and the device is released on exit
    """

    connected_gamepad.get_axis.side_effect = [
        *axes,
        1.0,
        -1.0,
        -1.0,
        -1.0,
    ].__getitem__

    run_game(max_frames=1)

    state = scene.call_args.args[2]
    if action is None:
        assert state.animation is None
    else:
        assert state.animation is not None
        assert state.animation.action is action
    connected_gamepad.get_instance_id.assert_called_once()
    connected_gamepad.quit.assert_called_once()
    assert not pygame.get_init()


@pytest.mark.parametrize(
    "x_axis, facing", [(-1.0, Direction.NORTH), (1.0, Direction.SOUTH)]
)
def test_held_turn_has_half_second_repeat_delay(
    monkeypatch: pytest.MonkeyPatch,
    connected_gamepad: Mock,
    scene: Mock,
    x_axis: float,
    facing: Direction,
) -> None:
    """FR-APP-002
    Feature: Held joystick turn repeat
    Scenario: A held turn waits half a second before repeating
    GIVEN a horizontal stick held in one direction
    WHEN the initial turn completes before its repeat deadline
    THEN no second turn begins until 0.5 seconds after the first start
    """

    clock = Mock()
    clock.tick.return_value = 16
    monkeypatch.setattr(pygame.time, "Clock", lambda: clock)
    connected_gamepad.get_axis.side_effect = [
        x_axis,
        0.0,
        0.0,
        0.0,
        -1.0,
        -1.0,
    ].__getitem__
    run_game(max_frames=33)

    for frame in range(ANIMATION_STEPS - 1, 32):
        state = scene.call_args_list[frame].args[2]
        assert state.facing is facing
        assert state.animation is None
    assert scene.call_args.args[2].animation is not None


@pytest.mark.parametrize("input_state", ["held", "released", "removed"])
def test_gamepad_hold_release_and_disconnect(
    monkeypatch: pytest.MonkeyPatch,
    connected_gamepad: Mock,
    scene: Mock,
    input_state: str,
) -> None:
    """FR-APP-001
    Feature: Polled gamepad movement
    Scenario: Holding, releasing, or disconnecting updates repeated input
    GIVEN a controller turning while its stick is held
    WHEN the stick is held, released, or the device is removed
    THEN no stale input starts an unintended turn and the device is closed
    """

    clock = Mock()
    clock.tick.return_value = 16
    monkeypatch.setattr(pygame.time, "Clock", lambda: clock)
    axes = [-1.0, 0.0, 0.0, 0.0, -1.0, -1.0]
    connected_gamepad.get_axis.side_effect = axes.__getitem__
    frames = 0

    def next_events() -> list[pygame.event.Event]:
        nonlocal frames
        frames += 1
        if frames == ANIMATION_STEPS + 1:
            if input_state == "released":
                axes[0] = 0.0
            elif input_state == "removed":
                return [
                    pygame.event.Event(pygame.JOYDEVICEREMOVED, instance_id=42)
                ]
        return []

    monkeypatch.setattr(pygame.event, "get", next_events)
    run_game(max_frames=ANIMATION_STEPS + 2)

    completed = scene.call_args_list[ANIMATION_STEPS - 1].args[2]
    assert completed.facing is Direction.NORTH
    assert completed.animation is None
    final = scene.call_args.args[2]
    assert final.animation is None
    assert final.facing is Direction.NORTH
    connected_gamepad.quit.assert_called_once()


def test_gamepad_connected_after_startup(
    monkeypatch: pytest.MonkeyPatch, connected_gamepad: Mock, scene: Mock
) -> None:
    """FR-APP-001
    Feature: Gamepad hot-plugging
    Scenario: A controller connected after startup becomes usable
    GIVEN no controller at startup
    WHEN a device-added event arrives
    THEN the newly connected stick can begin a game action
    """

    monkeypatch.setattr(pygame.joystick, "get_count", lambda: 0)
    connected_gamepad.get_axis.side_effect = [
        1.0,
        0.0,
        0.0,
        0.0,
        -1.0,
        -1.0,
    ].__getitem__
    monkeypatch.setattr(
        pygame.event,
        "get",
        lambda: [pygame.event.Event(pygame.JOYDEVICEADDED, device_index=0)],
    )
    run_game(max_frames=1)
    state = scene.call_args.args[2]
    assert state.animation.action is Action.TURN_RIGHT
    connected_gamepad.quit.assert_called_once()


@pytest.mark.parametrize(
    "event_type",
    [pygame.KEYDOWN, pygame.JOYBUTTONDOWN, pygame.CONTROLLERBUTTONDOWN],
)
@pytest.mark.parametrize("countdown_finished", [False, True])
def test_game_loop_restart_after_countdown(
    monkeypatch: pytest.MonkeyPatch,
    connected_gamepad: Mock,
    scene: Mock,
    event_type: int,
    countdown_finished: bool,
) -> None:
    """FR-APP-004
    Feature: Restart after victory
    Scenario: Eligible input restarts only after the countdown
    GIVEN a solved game before or after countdown completion
    WHEN a key or gamepad button event is processed
        THEN a fresh maze starts only after completion
        AND the triggering press does not move it
    """

    maze = generate_maze(seed=901)
    fresh_maze = generate_maze(seed=902)
    fresh_state = initial_state(fresh_maze)
    solved = replace(
        initial_state(maze),
        solved=True,
        solution_elapsed=(
            SOLUTION_COUNTDOWN_DURATION if countdown_finished else 0.0
        ),
    )
    generate = Mock(side_effect=[maze, fresh_maze])
    monkeypatch.setattr(game_app, "generate_maze", generate)
    monkeypatch.setattr(
        game_app, "initial_state", Mock(side_effect=[solved, fresh_state])
    )
    connected_gamepad.get_axis.side_effect = [
        -1.0,
        0.0,
        0.0,
        0.0,
        -1.0,
        -1.0,
    ].__getitem__
    monkeypatch.setattr(
        pygame.event,
        "get",
        lambda: [
            pygame.event.Event(event_type, key=pygame.K_w, button=15),
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w),
        ],
    )

    run_game(max_frames=1)

    state = scene.call_args.args[2]
    assert generate.call_count == (2 if countdown_finished else 1)
    if countdown_finished:
        assert state == fresh_state
        assert scene.call_args.args[1] is fresh_maze
    else:
        assert state.solved
        assert state.animation is None
    connected_gamepad.quit.assert_called_once()


@pytest.mark.parametrize(
    "connection_event", [pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED]
)
def test_restart_preserves_queued_connection_changes(
    monkeypatch: pytest.MonkeyPatch,
    connected_gamepad: Mock,
    scene: Mock,
    connection_event: int,
) -> None:
    """FR-APP-005
    Feature: Restart event handling
    Scenario: Restart does not discard queued connection changes
    GIVEN a completed game with restart and device lifecycle events queued
    WHEN the restart event is consumed
    THEN subsequent connection changes are still handled
    """

    maze = generate_maze(seed=904)
    fresh_maze = generate_maze(seed=905)
    fresh_state = initial_state(fresh_maze)
    solved = replace(
        initial_state(maze),
        solved=True,
        solution_elapsed=SOLUTION_COUNTDOWN_DURATION,
    )
    monkeypatch.setattr(
        game_app, "generate_maze", Mock(side_effect=[maze, fresh_maze])
    )
    monkeypatch.setattr(
        game_app, "initial_state", Mock(side_effect=[solved, fresh_state])
    )
    connected_gamepad.get_axis.side_effect = [
        -1.0,
        0.0,
        0.0,
        0.0,
        -1.0,
        -1.0,
    ].__getitem__
    added = connection_event == pygame.JOYDEVICEADDED
    monkeypatch.setattr(
        pygame.joystick, "get_count", lambda: 0 if added else 1
    )
    events = iter(
        [
            [
                pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w),
                pygame.event.Event(
                    connection_event, device_index=0, instance_id=42
                ),
            ],
            [],
        ]
    )
    monkeypatch.setattr(pygame.event, "get", lambda: next(events))

    run_game(max_frames=2)

    assert scene.call_args_list[0].args[2] == fresh_state
    state = scene.call_args.args[2]
    if added:
        assert state.animation is not None
        assert state.animation.action is Action.TURN_LEFT
    else:
        assert state == fresh_state
    connected_gamepad.get_instance_id.assert_called_once()
    connected_gamepad.quit.assert_called_once()


def test_quit_remains_active_after_restart(
    monkeypatch: pytest.MonkeyPatch, connected_gamepad: Mock, scene: Mock
) -> None:
    """FR-APP-003
    Feature: Application event handling
    Scenario: Window close remains effective after restart input
    GIVEN queued restart and window-close events
    WHEN the game loop processes them
    THEN the close event stops the loop
    """

    maze = generate_maze(seed=906)
    solved = replace(
        initial_state(maze),
        solved=True,
        solution_elapsed=SOLUTION_COUNTDOWN_DURATION,
    )
    monkeypatch.setattr(
        game_app,
        "initial_state",
        Mock(side_effect=[solved, initial_state(maze)]),
    )
    monkeypatch.setattr(
        pygame.event,
        "get",
        lambda: [
            pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w),
            pygame.event.Event(pygame.QUIT),
        ],
    )
    run_game(max_frames=2)
    scene.assert_not_called()
    connected_gamepad.quit.assert_called_once()


def test_game_closes_gamepad_on_render_error(
    connected_gamepad: Mock, scene: Mock
) -> None:
    """NFR-APP-001
    Feature: Application resource lifecycle
    Scenario: Rendering errors release game resources
    GIVEN an open gamepad and a renderer that raises an error
    WHEN the game loop exits exceptionally
    THEN the error propagates and both the device and pygame are closed
    """

    scene.side_effect = RuntimeError("draw failed")
    with pytest.raises(RuntimeError, match="draw failed"):
        run_game(max_frames=1)
    connected_gamepad.quit.assert_called_once()
    assert not pygame.get_init()


def test_gamepad_can_connect_during_countdown(
    monkeypatch: pytest.MonkeyPatch, connected_gamepad: Mock, scene: Mock
) -> None:
    """FR-APP-001
    Feature: Gamepad hot-plugging
    Scenario: Device lifecycle events remain active during victory countdown
    GIVEN a solved game and no currently connected controller
    WHEN a device-added event arrives during the countdown
    THEN the controller is opened while gameplay remains solved
    """

    maze = generate_maze(seed=903)
    solved = replace(initial_state(maze), solved=True, solution_elapsed=0.0)

    def solved_state(_maze: Maze) -> GameState:
        return solved

    monkeypatch.setattr(game_app, "initial_state", solved_state)
    monkeypatch.setattr(pygame.joystick, "get_count", lambda: 0)
    monkeypatch.setattr(
        pygame.event,
        "get",
        lambda: [pygame.event.Event(pygame.JOYDEVICEADDED, device_index=0)],
    )
    run_game(max_frames=1)
    assert scene.call_args.args[2].solved
    connected_gamepad.get_instance_id.assert_called_once()
    connected_gamepad.quit.assert_called_once()


def test_game_closes_gamepad_on_read_error(
    connected_gamepad: Mock,
) -> None:
    """NFR-APP-001
    Feature: Application resource lifecycle
    Scenario: Controller read errors release game resources
    GIVEN an open gamepad whose axis read raises an error
    WHEN the game loop exits exceptionally
    THEN the error propagates and both the device and pygame are closed
    """

    connected_gamepad.get_axis.side_effect = pygame.error("read failed")
    with pytest.raises(pygame.error, match="read failed"):
        run_game(max_frames=1)
    connected_gamepad.quit.assert_called_once()
    assert not pygame.get_init()


def test_key_event_starts_action(maze: Maze) -> None:
    """FR-APP-003
    Feature: Keyboard event handling
    Scenario: A supported key begins its game action
    GIVEN an active game and a forward key-down event
    WHEN the event is handled
    THEN a forward animation begins and the loop remains active
    """

    state = initial_state(maze)
    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w)
    updated, _, running = handle_event(event, state, maze, {})
    assert running
    assert updated.animation is not None
    assert updated.animation.action is Action.FORWARD


def test_any_key_restarts_a_solved_game(
    maze: Maze, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-APP-004
    Feature: Restart after victory
    Scenario: Any key restarts after countdown completion
    GIVEN a solved game whose countdown is complete
    WHEN any key-down event is handled
    THEN a fresh maze and initial state replace the solved game
    """

    fresh_maze = generate_maze(seed=901)
    monkeypatch.setattr(game_app, "generate_maze", lambda: fresh_maze)
    solved = replace(
        initial_state(maze, (13, 8), Direction.SOUTH),
        solved=True,
        solution_elapsed=SOLUTION_COUNTDOWN_DURATION,
    )
    axes = {0: [0.0, -1.0]}
    event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)

    updated, updated_maze, running = handle_event(event, solved, maze, axes)

    assert running
    assert updated_maze is fresh_maze
    assert updated == initial_state(fresh_maze)
    assert not updated.solved
    assert not axes


def test_key_is_ignored_during_solution_countdown(maze: Maze) -> None:
    """FR-APP-004
    Feature: Restart after victory
    Scenario: Keyboard input is ignored during the countdown
    GIVEN a solved game before countdown completion
    WHEN a key-down event is handled
    THEN the state remains solved and unchanged
    """

    state = replace(initial_state(maze), solved=True, solution_elapsed=0.0)
    updated, _, running = handle_event(
        pygame.event.Event(pygame.KEYDOWN, key=pygame.K_w), state, maze, {}
    )
    assert running
    assert updated is state


@pytest.mark.parametrize(
    "event_type", [pygame.JOYBUTTONDOWN, pygame.CONTROLLERBUTTONDOWN]
)
@pytest.mark.parametrize("button", range(16))
@pytest.mark.parametrize("elapsed", [0.0, SOLUTION_COUNTDOWN_DURATION - 0.001])
def test_gamepad_button_is_ignored_during_solution_countdown(
    maze: Maze, event_type: int, button: int, elapsed: float
) -> None:
    """FR-APP-004
    Feature: Restart after victory
    Scenario: Gamepad buttons are ignored during the countdown
    GIVEN a solved game before countdown completion
    WHEN a joystick or controller button-down event is handled
    THEN the state remains solved and unchanged
    """

    state = replace(initial_state(maze), solved=True, solution_elapsed=elapsed)
    event = pygame.event.Event(event_type, button=button)
    updated, _, running = handle_event(event, state, maze, {})
    assert running
    assert updated is state


@pytest.mark.parametrize(
    "event_type", [pygame.JOYBUTTONDOWN, pygame.CONTROLLERBUTTONDOWN]
)
@pytest.mark.parametrize("button", range(16))
def test_gamepad_button_restarts_after_countdown(
    maze: Maze,
    event_type: int,
    button: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-APP-004
    Feature: Restart after victory
    Scenario: A gamepad button restarts after countdown completion
    GIVEN a solved game whose countdown is complete
    WHEN a joystick or controller button-down event is handled
    THEN a fresh maze and initial state replace the solved game
    """

    fresh_maze = generate_maze(seed=902)
    monkeypatch.setattr(game_app, "generate_maze", lambda: fresh_maze)
    state = replace(
        initial_state(maze),
        solved=True,
        solution_elapsed=SOLUTION_COUNTDOWN_DURATION,
    )
    axes = {0: [0.0, -1.0]}
    event = pygame.event.Event(event_type, button=button)
    updated, updated_maze, running = handle_event(event, state, maze, axes)
    assert running
    assert updated_maze is fresh_maze
    assert updated == initial_state(fresh_maze)
    assert not axes


@pytest.mark.parametrize(
    "event_type",
    [
        pygame.JOYBUTTONUP,
        pygame.CONTROLLERBUTTONUP,
        pygame.JOYAXISMOTION,
        pygame.JOYHATMOTION,
    ],
)
def test_gamepad_release_or_motion_does_not_restart(
    maze: Maze, event_type: int
) -> None:
    """FR-APP-004
    Feature: Restart after victory
    Scenario: Release and motion events do not restart a completed game
    GIVEN a solved game whose countdown is complete
    WHEN a gamepad release, axis, or hat event is handled
    THEN the maze and state remain unchanged
    """

    state = replace(
        initial_state(maze),
        solved=True,
        solution_elapsed=SOLUTION_COUNTDOWN_DURATION,
    )
    updated, updated_maze, running = handle_event(
        pygame.event.Event(event_type), state, maze, {}
    )
    assert updated is state
    assert updated_maze is maze
    assert running


def test_quit_event_stops_loop(maze: Maze) -> None:
    """FR-APP-003
    Feature: Application event handling
    Scenario: A window-close event stops the game loop
    GIVEN an active game
    WHEN a pygame quit event is handled
    THEN the loop stops without replacing maze or state
    """

    state = initial_state(maze)
    updated, updated_maze, running = handle_event(
        pygame.event.Event(pygame.QUIT), state, maze, {}
    )
    assert not running
    assert updated is state
    assert updated_maze is maze


def test_stale_axis_events_do_not_override_polled_input(
    monkeypatch: pytest.MonkeyPatch, connected_gamepad: Mock, scene: Mock
) -> None:
    """FR-APP-001
    Feature: Polled gamepad movement
    Scenario: Current axis polling takes precedence over stale events
    GIVEN a stale queued axis-motion event and a centered current stick
    WHEN the game loop processes a frame
    THEN no action begins from the stale event value
    """

    connected_gamepad.get_axis.side_effect = [
        0.0,
        0.0,
        0.0,
        0.0,
        -1.0,
        -1.0,
    ].__getitem__
    monkeypatch.setattr(
        pygame.event,
        "get",
        lambda: [
            pygame.event.Event(
                pygame.JOYAXISMOTION, instance_id=42, axis=1, value=-1.0
            )
        ],
    )
    run_game(max_frames=1)
    assert scene.call_args.args[2].animation is None


def test_joystick_hat_event_starts_turn(maze: Maze) -> None:
    """FR-APP-003
    Feature: Joystick hat event handling
    Scenario: A horizontal hat event begins a turn
    GIVEN an active game and a left hat-motion event
    WHEN the event is handled
    THEN a left-turn animation begins
    """

    state = initial_state(maze)
    event = pygame.event.Event(pygame.JOYHATMOTION, value=(-1, 0))
    updated, _, running = handle_event(event, state, maze, {})
    assert running
    assert updated.animation is not None
    assert updated.animation.action is Action.TURN_LEFT


def test_irrelevant_event_does_not_change_state(maze: Maze) -> None:
    """FR-APP-003
    Feature: Application event handling
    Scenario: Unmapped events do not change game state
    GIVEN an active game and an unrelated mouse event
    WHEN the event is handled
    THEN the state remains unchanged and the loop continues
    """

    state = initial_state(maze)
    event = pygame.event.Event(pygame.MOUSEMOTION, pos=(0, 0))
    updated, _, running = handle_event(event, state, maze, {})
    assert running
    assert updated is state


def test_held_joystick_starts_another_action(maze: Maze) -> None:
    """FR-APP-001
    Feature: Polled gamepad movement
    Scenario: Held stick input starts an action when the game is idle
    GIVEN an idle game and a deflected left stick
    WHEN held axes are applied
    THEN the matching action begins
    """

    state = initial_state(maze)
    updated = apply_held_axes(state, maze, {0: [0.0, -1.0]}, {}, 0.0)
    assert updated.animation is not None
    assert updated.animation.action is Action.FORWARD


def test_held_joystick_waits_until_animation_finishes(maze: Maze) -> None:
    """FR-APP-001
    Feature: Polled gamepad movement
    Scenario: Held input waits for the current animation
    GIVEN a game with an action animation in progress
    WHEN held axes are applied
    THEN no overlapping action begins
    """

    state = begin_action(initial_state(maze), maze, Action.TURN_LEFT)
    assert apply_held_axes(state, maze, {0: [0.0, -1.0]}, {}, 0.0) is state


def test_centered_joystick_does_not_start_action(maze: Maze) -> None:
    """FR-APP-001
    Feature: Polled gamepad movement
    Scenario: A centered stick does not start an action
    GIVEN a centered left stick
    WHEN held axes are applied
    THEN the state remains idle
    """

    state = initial_state(maze)
    assert apply_held_axes(state, maze, {0: [0.0, 0.0]}, {}, 0.0) is state


def test_idle_controller_does_not_block_another_gamepad(maze: Maze) -> None:
    """FR-APP-001
    Feature: Multiple gamepad input
    Scenario: An idle controller does not block another controller
    GIVEN one centered controller and one deflected controller
    WHEN held axes are applied
    THEN the deflected controller can begin its action
    """

    state = apply_held_axes(
        initial_state(maze),
        maze,
        {42: [0.0, 0.0], 99: [-1.0, 0.0]},
        {},
        0.0,
    )
    assert state.animation is not None
    assert state.animation.action is Action.TURN_LEFT


@pytest.mark.parametrize("x_axis", [-1.0, 1.0])
@pytest.mark.parametrize(
    "offset, repeats", [(0.001, False), (0.499, False), (0.5, True)]
)
def test_turn_repeat_deadline(
    maze: Maze, x_axis: float, offset: float, repeats: bool
) -> None:
    """FR-APP-002
    Feature: Held joystick turn repeat
    Scenario: A held turn repeats at its half-second deadline
    GIVEN a turn started by a held horizontal axis
    WHEN the repeat deadline has or has not elapsed
    THEN another turn begins only at or after 0.5 seconds
    """

    timers: dict[int, tuple[Action, float]] = {}
    axes = {42: [x_axis, 0.0]}
    state = apply_held_axes(initial_state(maze), maze, axes, timers, 10.0)
    assert state.animation is not None
    for _ in range(ANIMATION_STEPS):
        state = advance_animation(state, maze)
    updated = apply_held_axes(state, maze, axes, timers, 10.0 + offset)
    if repeats:
        assert updated.animation is not None
        assert updated.animation.action is (
            Action.TURN_LEFT if x_axis < 0 else Action.TURN_RIGHT
        )
    else:
        assert updated is state
        assert timers[42][1] == 10.5


@pytest.mark.parametrize("released_axes", [{}, {42: [0.0, 0.0]}])
def test_release_or_disconnect_during_animation_resets_turn_delay(
    maze: Maze, released_axes: dict[int, list[float]]
) -> None:
    """FR-APP-002
    Feature: Held joystick turn repeat
    Scenario: Release or disconnect resets the turn deadline
    GIVEN a turn repeat deadline while an animation is active
    WHEN the controller is released or removed
    THEN a later deflection can turn immediately
    """

    timers: dict[int, tuple[Action, float]] = {}
    held_axes = {42: [-1.0, 0.0]}
    state = apply_held_axes(initial_state(maze), maze, held_axes, timers, 10.0)
    assert timers
    assert apply_held_axes(state, maze, released_axes, timers, 10.05) is state
    assert not timers
    for _ in range(ANIMATION_STEPS):
        state = advance_animation(state, maze)
    updated = apply_held_axes(state, maze, held_axes, timers, 10.2)
    assert updated.animation is not None
    assert updated.animation.action is Action.TURN_LEFT


def test_opposite_turn_is_immediate(maze: Maze) -> None:
    """FR-APP-002
    Feature: Held joystick turn repeat
    Scenario: Changing direction starts a turn immediately
    GIVEN a pending repeat deadline for one turn direction
    WHEN the stick changes to the opposite direction
    THEN the opposite turn begins without waiting for that deadline
    """

    timers = {42: (Action.TURN_LEFT, 10.5)}
    state = apply_held_axes(
        initial_state(maze), maze, {42: [1.0, 0.0]}, timers, 10.2
    )
    assert state.animation is not None
    assert state.animation.action is Action.TURN_RIGHT


@pytest.mark.parametrize(
    "y_axis, action", [(-1.0, Action.FORWARD), (1.0, Action.BACKWARD)]
)
def test_walking_repeats_without_turn_delay(
    maze: Maze, y_axis: float, action: Action
) -> None:
    """FR-APP-002
    Feature: Held joystick movement repeat
    Scenario: Walking repeats without the turn throttle
    GIVEN a held forward or backward axis
    WHEN the prior walking animation completes before a turn deadline
    THEN the next walking action begins without an extra delay
    """

    timers = {42: (Action.TURN_LEFT, 10.5)}
    axes = {42: [0.0, y_axis]}
    state = apply_held_axes(
        initial_state(maze, (3, 1), Direction.EAST),
        maze,
        axes,
        timers,
        10.0,
    )
    for _ in range(ANIMATION_STEPS):
        state = advance_animation(state, maze)
    updated = apply_held_axes(state, maze, axes, timers, 10.15)
    assert updated.animation is not None
    assert updated.animation.action is action
    assert not timers


def test_turn_delay_is_per_controller(maze: Maze) -> None:
    """FR-APP-002
    Feature: Multiple gamepad turn repeat
    Scenario: Turn repeat deadlines are tracked per controller
    GIVEN two controllers with independent turn states
    WHEN one controller is still waiting and the other requests a turn
    THEN the second controller can start its turn independently
    """

    timers = {42: (Action.TURN_LEFT, 10.5)}
    state = apply_held_axes(
        initial_state(maze),
        maze,
        {42: [-1.0, 0.0], 99: [1.0, 0.0]},
        timers,
        10.2,
    )
    assert state.animation is not None
    assert state.animation.action is Action.TURN_RIGHT
    assert timers[42] == (Action.TURN_LEFT, 10.5)
    assert timers[99] == (Action.TURN_RIGHT, 10.7)


def test_busy_game_does_not_consume_turn_repeat(maze: Maze) -> None:
    """FR-APP-002
    Feature: Held joystick turn repeat
    Scenario: A busy game does not consume a repeat deadline
    GIVEN an animation already in progress
    WHEN a held turn is polled
    THEN no repeat timer is created until a turn actually starts
    """

    timers: dict[int, tuple[Action, float]] = {}
    state = begin_action(initial_state(maze), maze, Action.TURN_LEFT)
    assert (
        apply_held_axes(state, maze, {42: [-1.0, 0.0]}, timers, 10.0) is state
    )
    assert not timers


def test_solved_game_does_not_consume_turn_repeat(maze: Maze) -> None:
    """FR-APP-002
    Feature: Held joystick turn repeat
    Scenario: A solved game does not consume a repeat deadline
    GIVEN a solved game and a deflected horizontal stick
    WHEN held axes are applied
    THEN no turn starts and no repeat timer is created
    """

    timers: dict[int, tuple[Action, float]] = {}
    state = replace(initial_state(maze), solved=True)
    assert (
        apply_held_axes(state, maze, {42: [-1.0, 0.0]}, timers, 10.0) is state
    )
    assert not timers


def test_run_game_can_execute_headlessly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NFR-TEST-001
    Feature: Headless application testability
    Scenario: The bounded game loop runs without display or audio hardware
    GIVEN SDL dummy video and audio drivers
    WHEN the game loop runs for one bounded frame
    THEN it completes without requiring physical hardware
    """

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setattr(pygame.joystick, "get_count", lambda: 0)
    run_game(max_frames=1)


def test_run_game_exits_on_quit_event(monkeypatch: pytest.MonkeyPatch) -> None:
    """FR-APP-003
    Feature: Application event handling
    Scenario: A queued window-close event exits the real loop
    GIVEN the game loop with a queued pygame quit event
    WHEN the event is processed
    THEN the application exits and releases pygame
    """

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setattr(pygame.joystick, "get_count", lambda: 0)
    pygame.init()
    pygame.event.post(pygame.event.Event(pygame.QUIT))
    run_game()
