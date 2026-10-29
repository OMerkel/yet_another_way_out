"""Pygame event loop and application composition."""

from __future__ import annotations

import pygame

from .gamepad import Gamepads
from .input import TURN_REPEAT_SECONDS, action_for_axes, action_for_key
from .model import (
    Action,
    GameState,
    Maze,
    advance_animation,
    advance_solution_timer,
    begin_action,
    generate_maze,
    initial_state,
    solution_countdown,
)
from .rendering import SCREEN_SIZE, draw_scene


def handle_event(
    event: pygame.event.Event,
    state: GameState,
    maze: Maze,
    axes: dict[int, list[float]],
) -> tuple[GameState, Maze, bool]:
    """Apply one input event and report whether the loop should continue."""

    if event.type == pygame.QUIT:
        return state, maze, False
    if state.solved:
        restart_events = (
            pygame.KEYDOWN,
            pygame.JOYBUTTONDOWN,
            pygame.CONTROLLERBUTTONDOWN,
        )
        if solution_countdown(state) is None and event.type in restart_events:
            maze = generate_maze()
            axes.clear()
            return initial_state(maze), maze, True
        return state, maze, True
    action = None
    if event.type == pygame.KEYDOWN:
        action = action_for_key(event.key)
    elif event.type == pygame.JOYHATMOTION:
        action = action_for_axes(event.value[0], -event.value[1])
    if action is not None:
        state = begin_action(state, maze, action)
    return state, maze, True


def apply_held_axes(
    state: GameState,
    maze: Maze,
    axes: dict[int, list[float]],
    turn_repeats: dict[int, tuple[Action, float]],
    now: float,
) -> GameState:
    """Repeat held walking freely and held turns at half-second intervals."""

    actions: dict[int, Action | None] = {
        device_id: action_for_axes(*device_axes)
        for device_id, device_axes in axes.items()
    }
    for device_id, (held_action, _) in tuple(turn_repeats.items()):
        if actions.get(device_id) != held_action:
            del turn_repeats[device_id]
    if state.animation is not None or state.solved:
        return state
    for device_id, action in actions.items():
        if action is None:
            continue
        is_turn = action in (Action.TURN_LEFT, Action.TURN_RIGHT)
        repeat = turn_repeats.get(device_id)
        if is_turn and repeat is not None and now < repeat[1]:
            continue
        updated = begin_action(state, maze, action)
        if is_turn and updated is not state:
            turn_repeats[device_id] = (action, now + TURN_REPEAT_SECONDS)
        return updated
    return state


def run_game(max_frames: int | None = None) -> None:
    """Run the game; max_frames is a deterministic test seam."""

    pygame.init()
    gamepads = Gamepads()
    try:
        screen = pygame.display.set_mode(SCREEN_SIZE)
        pygame.display.set_caption("Yet Another Way Out")
        clock = pygame.time.Clock()
        gamepads.open_connected()
        maze = generate_maze()
        state = initial_state(maze)
        axes: dict[int, list[float]] = {}
        turn_repeats: dict[int, tuple[Action, float]] = {}
        elapsed = 0.0
        frame_count = 0
        running = True
        while running and (max_frames is None or frame_count < max_frames):
            delta_seconds = min(clock.tick(60) / 1000, 0.1)
            elapsed += delta_seconds
            state = advance_solution_timer(state, delta_seconds)
            was_solved = state.solved
            for event in pygame.event.get():
                gamepads.handle_event(event)
                if (
                    was_solved
                    and not state.solved
                    and event.type != pygame.QUIT
                ):
                    continue
                state, maze, running = handle_event(event, state, maze, axes)
                if not running:
                    break
            if not running:
                break
            if was_solved and not state.solved:
                turn_repeats.clear()
            if not was_solved:
                axes = gamepads.left_sticks()
                state = apply_held_axes(
                    state, maze, axes, turn_repeats, elapsed
                )
            state = advance_animation(state, maze)
            draw_scene(screen, maze, state, elapsed)
            pygame.display.flip()
            frame_count += 1
    finally:
        gamepads.close()
        pygame.quit()


def main() -> None:
    """Start the game application."""

    run_game()
