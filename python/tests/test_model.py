"""Tests for pure maze and state transitions."""

from dataclasses import FrozenInstanceError, replace

import pytest

from way_out_game.model import (
    ANIMATION_STEPS,
    DEFAULT_MAZE_HEIGHT,
    DEFAULT_MAZE_WIDTH,
    SOLUTION_COUNTDOWN_DURATION,
    Action,
    Animation,
    Direction,
    GameState,
    Maze,
    advance_animation,
    advance_solution_timer,
    begin_action,
    direction_vector,
    generate_maze,
    initial_state,
    solution_countdown,
    step,
    view_pose,
    visible_cells,
)


def _assign_attribute(target: object, name: str, value: object) -> None:
    """Attempt a dynamic assignment for frozen-dataclass tests."""

    setattr(target, name, value)


def test_generated_maze_has_scaled_dimensions_and_one_exit() -> None:
    """FR-MAZ-001
    Feature: Procedural maze generation
    Scenario: Generate the default playable maze
    GIVEN no custom dimensions are supplied
    WHEN a maze is generated
    THEN it is 23 by 17 with one reachable wall exit and a valid floor entry
    """

    generated = generate_maze(seed=37)
    assert generated.width == DEFAULT_MAZE_WIDTH == 23
    assert generated.height == DEFAULT_MAZE_HEIGHT == 17
    assert generated.tile(generated.exit_position) == "E"
    assert generated.tile(generated.entry_position) == "."
    assert (
        generated.tile(step(generated.entry_position, generated.entry_facing))
        == "."
    )
    exit_x, exit_y = generated.exit_position
    assert 0 < exit_x < generated.width - 1
    assert 0 < exit_y < generated.height - 1
    assert any(
        generated.tile(step(generated.exit_position, direction)) == "."
        for direction in Direction
    )
    assert generated.tile((-1, 0)) == "#"
    state = initial_state(generated)
    assert state.position == generated.entry_position
    assert state.facing is generated.entry_facing


def test_maze_generation_is_seeded_and_randomized() -> None:
    """FR-MAZ-002
    Feature: Reproducible maze generation
    Scenario: A seed reproduces its maze
    GIVEN a maze generation seed
    WHEN mazes are generated with the same and different seeds
    THEN the same seed repeats its layout and other seeds can vary it
    """

    layouts = [generate_maze(seed=seed) for seed in range(10, 20)]
    assert layouts[0] == generate_maze(seed=10)
    assert len({maze.entry_position for maze in layouts}) > 1
    assert len({maze.exit_position for maze in layouts}) > 1


def test_generated_exit_is_reachable_from_the_start() -> None:
    """FR-MAZ-003
    Feature: Reachable maze exit
    Scenario: Generated passages connect entry to exit
    GIVEN a generated maze
    WHEN its floor and exit cells are traversed
    THEN the exit is reachable from the entry
    """

    generated = generate_maze(seed=73)
    pending = [generated.entry_position]
    reached = {generated.entry_position}
    while pending:
        x, y = pending.pop()
        for direction in Direction:
            neighbor = step((x, y), direction)
            if neighbor in reached:
                continue
            if generated.tile(neighbor) not in (".", "E"):
                continue
            reached.add(neighbor)
            pending.append(neighbor)
    assert generated.exit_position in reached


@pytest.mark.parametrize("dimensions", [(6, 9), (9, 6), (8, 8)])
def test_maze_generator_rejects_even_or_too_small_dimensions(
    dimensions: tuple[int, int],
) -> None:
    """FR-MAZ-004
    Feature: Maze dimension validation
    Scenario: Invalid generation dimensions are rejected
    GIVEN dimensions that are even or smaller than seven
    WHEN maze generation is requested
    THEN a ValueError is raised
    """

    with pytest.raises(ValueError):
        generate_maze(*dimensions)


@pytest.mark.parametrize(
    "rows, exit_position",
    [
        ((), (0, 0)),
        (("..", "."), (0, 0)),
        ((".X",), (0, 0)),
        (("E.",), (1, 0)),
        (("..",), (1, 0)),
    ],
)
def test_maze_rejects_invalid_layouts(
    rows: tuple[str, ...], exit_position: tuple[int, int]
) -> None:
    """FR-MAZ-004
    Feature: Maze layout validation
    Scenario: Invalid tile grids or exit definitions are rejected
    GIVEN an empty, nonrectangular, invalid-tile, or wrongly exited layout
    WHEN a Maze is constructed
    THEN a ValueError is raised
    """

    with pytest.raises(ValueError):
        Maze(rows, exit_position)


def test_maze_rejects_entry_outside_the_grid() -> None:
    """FR-MAZ-004
    Feature: Maze layout validation
    Scenario: Entry metadata must identify an in-bounds floor cell
    GIVEN entry metadata outside the grid or on a non-floor tile
    WHEN a Maze is constructed
    THEN a ValueError is raised
    """

    with pytest.raises(ValueError):
        Maze(
            rows=("#####", "#.E.#", "#####"),
            exit_position=(2, 1),
            entry_position=(5, 1),
        )


def test_maze_is_immutable(maze: Maze) -> None:
    """NFR-DESIGN-001
    Feature: Immutable domain values
    Scenario: A validated maze cannot be mutated
    GIVEN a constructed Maze value
    WHEN a field is assigned
    THEN the frozen value rejects the mutation
    """

    with pytest.raises(FrozenInstanceError):
        _assign_attribute(maze, "exit_position", (1, 1))


@pytest.mark.parametrize(
    "direction, vector",
    [
        (Direction.NORTH, (0, -1)),
        (Direction.EAST, (1, 0)),
        (Direction.SOUTH, (0, 1)),
        (Direction.WEST, (-1, 0)),
    ],
)
def test_direction_vectors(
    direction: Direction, vector: tuple[int, int]
) -> None:
    """FR-ACT-001
    Feature: Cardinal movement geometry
    Scenario: Directions map to their grid vectors
    GIVEN any cardinal direction
    WHEN its vector and a stepped point are calculated
    THEN the point advances along that direction by the requested distance
    """

    assert direction_vector(direction) == vector
    assert step((4, 5), direction, 2) == (
        4 + vector[0] * 2,
        5 + vector[1] * 2,
    )


def test_initial_state_reveals_starting_corridor(maze: Maze) -> None:
    """FR-VIEW-001
    Feature: Explored maze view
    Scenario: A new game reveals its starting view
    GIVEN a maze with an entry position and heading
    WHEN the initial state is created
    THEN the player starts there and visible cells are explored
    """

    state = initial_state(maze)
    assert state.position == (1, 1)
    assert state.facing is Direction.EAST
    assert state.position in state.explored
    assert (2, 1) in state.explored


def test_initial_state_rejects_non_floor_position(maze: Maze) -> None:
    """FR-STATE-001
    Feature: Valid player state
    Scenario: The initial player position must be floor
    GIVEN a requested starting position on a wall
    WHEN the initial state is created
    THEN a ValueError is raised
    """

    with pytest.raises(ValueError):
        initial_state(maze, (0, 0))


def test_visible_cells_include_walls_and_side_panels(maze: Maze) -> None:
    """FR-VIEW-001
    Feature: Corridor visibility
    Scenario: Visibility includes the corridor and side panels
    GIVEN a player facing down a corridor
    WHEN visible cells are calculated
    THEN the forward wall, adjacent side panels, and player cell are included
    """

    visible = visible_cells(maze, (1, 1), Direction.NORTH)
    assert (1, 0) in visible
    assert (0, 0) in visible
    assert (1, 1) in visible
    assert (1, 2) not in visible


def test_visible_cells_stop_at_wall(maze: Maze) -> None:
    """FR-VIEW-001
    Feature: Corridor visibility
    Scenario: Visibility stops at the first blocking cell
    GIVEN a corridor with a wall ahead
    WHEN visibility is calculated beyond that wall
    THEN cells beyond the wall are not revealed
    """

    visible = visible_cells(maze, (1, 1), Direction.NORTH, depth=20)
    assert (1, 0) in visible
    assert (1, -1) not in visible


def test_visible_cells_with_zero_depth_contains_only_player(
    maze: Maze,
) -> None:
    """FR-VIEW-001
    Feature: Corridor visibility
    Scenario: Zero view depth reveals only the player cell
    GIVEN a view depth of zero
    WHEN visible cells are calculated
    THEN the result contains only the player position
    """

    assert visible_cells(maze, (1, 1), Direction.EAST, depth=0) == frozenset(
        {(1, 1)}
    )


def test_begin_action_starts_eight_frame_animation(maze: Maze) -> None:
    """FR-ACT-001
    Feature: Animated player actions
    Scenario: An accepted action begins an eight-frame animation
    GIVEN an idle unsolved game
    WHEN the player begins a forward action
    THEN an eight-frame animation starts without immediately moving position
    """

    state = initial_state(maze)
    moving = begin_action(state, maze, Action.FORWARD)
    assert moving.animation == Animation(Action.FORWARD)
    assert moving.position == state.position
    assert ANIMATION_STEPS == 8


def test_blocked_move_does_not_change_state(maze: Maze) -> None:
    """FR-ACT-001
    Feature: Collision handling
    Scenario: A step into a wall is rejected
    GIVEN an idle player facing a wall
    WHEN forward movement is requested
    THEN the state is unchanged and no animation starts
    """

    state = initial_state(maze, (1, 1), Direction.NORTH)
    assert begin_action(state, maze, Action.FORWARD) is state


@pytest.mark.parametrize("action", [Action.TURN_LEFT, Action.TURN_RIGHT])
def test_actions_are_ignored_while_animating(
    maze: Maze, action: Action
) -> None:
    """FR-ACT-001
    Feature: Animated player actions
    Scenario: An active animation prevents overlapping actions
    GIVEN a player with an action in progress
    WHEN another action is requested
    THEN the current state is returned unchanged
    """

    state = begin_action(initial_state(maze), maze, Action.FORWARD)
    assert begin_action(state, maze, action) is state


def test_turn_commits_after_eight_frames(maze: Maze) -> None:
    """FR-ACT-001
    Feature: Animated player actions
    Scenario: A left turn commits on the eighth frame
    GIVEN a left-turn animation
    WHEN its first seven frames advance and then its eighth advances
    THEN facing changes only on completion and the animation clears
    """

    state = begin_action(initial_state(maze), maze, Action.TURN_LEFT)
    for _ in range(ANIMATION_STEPS - 1):
        state = advance_animation(state, maze)
    assert state.facing is Direction.EAST
    state = advance_animation(state, maze)
    assert state.facing is Direction.NORTH
    assert state.animation is None


def test_forward_commits_position_and_expands_map(maze: Maze) -> None:
    """FR-ACT-001
    Feature: Animated player actions
    Scenario: Forward movement commits and reveals the new view
    GIVEN an accepted forward animation
    WHEN all eight frames advance
    THEN position moves one cell and newly visible cells are explored
    """

    state = begin_action(initial_state(maze), maze, Action.FORWARD)
    for _ in range(ANIMATION_STEPS):
        state = advance_animation(state, maze)
    assert state.position == (2, 1)
    assert (3, 1) in state.explored
    assert state.animation is None


def test_backward_move_uses_opposite_direction(maze: Maze) -> None:
    """FR-ACT-001
    Feature: Animated player actions
    Scenario: Backward movement uses the opposite grid direction
    GIVEN a player on a corridor facing forward
    WHEN a backward action completes
    THEN position moves one cell backward and facing is unchanged
    """

    state = begin_action(initial_state(maze, (2, 1)), maze, Action.BACKWARD)
    for _ in range(ANIMATION_STEPS):
        state = advance_animation(state, maze)
    assert state.position == (1, 1)


def test_backward_move_can_reach_exit(maze: Maze) -> None:
    """FR-SOLVE-001
    Feature: Exit completion
    Scenario: Reaching the exit while moving backward solves the maze
    GIVEN the exit is behind the player
    WHEN the backward animation completes
    THEN the game is solved without moving into the exit wall
    """

    state = initial_state(maze, (13, 8), Direction.NORTH)
    state = begin_action(state, maze, Action.BACKWARD)
    for _ in range(ANIMATION_STEPS):
        state = advance_animation(state, maze)
    assert state.solved
    assert state.position == (13, 8)


def test_right_turn_commits_after_eight_frames(maze: Maze) -> None:
    """FR-ACT-001
    Feature: Animated player actions
    Scenario: A right turn commits on the eighth frame
    GIVEN a right-turn animation
    WHEN all eight frames advance
    THEN facing rotates clockwise and the animation clears
    """

    state = begin_action(initial_state(maze), maze, Action.TURN_RIGHT)
    for _ in range(ANIMATION_STEPS):
        state = advance_animation(state, maze)
    assert state.facing is Direction.SOUTH
    assert state.animation is None


def test_advance_without_animation_is_a_noop(maze: Maze) -> None:
    """FR-ACT-001
    Feature: Animated player actions
    Scenario: Advancing an idle state is a no-op
    GIVEN a state without an active animation
    WHEN one animation frame is advanced
    THEN the same state is returned
    """

    state = initial_state(maze)
    assert advance_animation(state, maze) is state


def test_exit_solves_without_entering_wall(maze: Maze) -> None:
    """FR-SOLVE-001
    Feature: Exit completion
    Scenario: Reaching the exit solves without entering its wall cell
    GIVEN the player is adjacent to the exit panel
    WHEN a movement animation reaches the exit
    THEN the player remains in the passage and the solved timer starts at zero
    """

    state = initial_state(maze, (13, 8), Direction.SOUTH)
    state = begin_action(state, maze, Action.FORWARD)
    for _ in range(ANIMATION_STEPS):
        state = advance_animation(state, maze)
    assert state.solved
    assert state.solution_elapsed == 0.0
    assert solution_countdown(state) == 10
    assert state.position == (13, 8)
    assert begin_action(state, maze, Action.TURN_LEFT) is state


@pytest.mark.parametrize(
    "elapsed, expected",
    [
        (0.0, 10),
        (0.49, 10),
        (0.5, 9),
        (4.5, 1),
        (SOLUTION_COUNTDOWN_DURATION, None),
    ],
)
def test_solution_countdown_steps_every_half_second(
    maze: Maze, elapsed: float, expected: int | None
) -> None:
    """FR-SOLVE-002
    Feature: Victory countdown
    Scenario: The countdown decreases every half second
    GIVEN a solved state at a countdown boundary or between boundaries
    WHEN the visible countdown is calculated
    THEN values run from 10 to 1 and disappear after five seconds
    """

    state = replace(initial_state(maze), solved=True, solution_elapsed=elapsed)
    assert solution_countdown(state) == expected


def test_solution_timer_advances_and_clamps(maze: Maze) -> None:
    """FR-SOLVE-002
    Feature: Victory countdown
    Scenario: The solved timer clamps at five seconds
    GIVEN a solved state near the end of its countdown
    WHEN elapsed time advances past the duration
    THEN elapsed time is clamped and the countdown is complete
    """

    state = replace(initial_state(maze), solved=True, solution_elapsed=4.8)
    state = advance_solution_timer(state, 1.0)
    assert state.solution_elapsed == SOLUTION_COUNTDOWN_DURATION
    assert solution_countdown(state) is None


def test_solution_timer_ignores_unsolved_state(maze: Maze) -> None:
    """FR-SOLVE-002
    Feature: Victory countdown
    Scenario: An unsolved game has no advancing win timer
    GIVEN an active unsolved state
    WHEN the solution timer advances
    THEN the same state is returned
    """

    state = initial_state(maze)
    assert advance_solution_timer(state, 0.5) is state


def test_solution_timer_is_a_noop_when_already_complete(maze: Maze) -> None:
    """FR-SOLVE-002
    Feature: Victory countdown
    Scenario: A completed countdown remains complete
    GIVEN a solved state at the full countdown duration
    WHEN additional time advances
    THEN the state remains unchanged
    """

    state = replace(
        initial_state(maze),
        solved=True,
        solution_elapsed=SOLUTION_COUNTDOWN_DURATION,
    )
    assert advance_solution_timer(state, 0.5) is state


def test_solution_countdown_is_hidden_before_a_win(maze: Maze) -> None:
    """FR-SOLVE-002
    Feature: Victory countdown
    Scenario: No countdown is shown before the exit is reached
    GIVEN an unsolved maze
    WHEN the countdown is queried
    THEN no countdown value is returned
    """

    assert solution_countdown(initial_state(maze)) is None


def test_view_pose_interpolates_movement(maze: Maze) -> None:
    """FR-ACT-002
    Feature: Animated camera pose
    Scenario: Camera position interpolates during a step
    GIVEN a forward animation at its initial frame
    WHEN one frame advances
    THEN camera position moves by one eighth of a cell
    """

    state = begin_action(initial_state(maze), maze, Action.FORWARD)
    start = view_pose(state)
    assert start[:2] == (1.5, 1.5)
    state = advance_animation(state, maze)
    after_one_frame = view_pose(state)
    assert after_one_frame[0] > start[0]
    assert after_one_frame[0] - start[0] == pytest.approx(1 / 8)


def test_view_pose_interpolates_turn(maze: Maze) -> None:
    """FR-ACT-002
    Feature: Animated camera pose
    Scenario: Camera heading interpolates during a turn
    GIVEN a right-turn animation at its initial frame
    WHEN one frame advances
    THEN the camera heading moves toward the target direction
    """

    state = begin_action(initial_state(maze), maze, Action.TURN_RIGHT)
    _, _, initial_heading = view_pose(state)
    state = advance_animation(state, maze)
    _, _, next_heading = view_pose(state)
    assert next_heading > initial_heading


def test_animation_rejects_invalid_frame() -> None:
    """FR-ACT-001
    Feature: Animated player actions
    Scenario: Animation frames stay within the valid range
    GIVEN a frame index equal to the animation length
    WHEN an Animation is constructed
    THEN a ValueError is raised
    """

    with pytest.raises(ValueError):
        Animation(Action.FORWARD, ANIMATION_STEPS)


def test_game_state_is_immutable(maze: Maze) -> None:
    """NFR-DESIGN-001
    Feature: Immutable domain values
    Scenario: A game state cannot be mutated in place
    GIVEN a constructed GameState value
    WHEN a field is assigned
    THEN the frozen value rejects the mutation
    """

    state = initial_state(maze)
    with pytest.raises(FrozenInstanceError):
        _assign_attribute(state, "solved", True)


def test_custom_state_cannot_move_into_outer_wall(maze: Maze) -> None:
    """FR-ACT-001
    Feature: Collision handling
    Scenario: Out-of-bounds cells behave as walls
    GIVEN a player facing beyond the maze boundary
    WHEN movement is requested
    THEN the state remains unchanged
    """

    state = GameState((1, 1), Direction.NORTH, frozenset())
    assert begin_action(state, maze, Action.FORWARD) is state
