"""Immutable maze state and deterministic game transitions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum, IntEnum
from math import pi
from random import Random

Point = tuple[int, int]
Vector = tuple[int, int]
ANIMATION_STEPS = 8
VIEW_DEPTH = 6
SOLUTION_COUNTDOWN_STEPS = 10
SOLUTION_COUNTDOWN_STEP_SECONDS = 0.5
SOLUTION_COUNTDOWN_DURATION = (
    SOLUTION_COUNTDOWN_STEPS * SOLUTION_COUNTDOWN_STEP_SECONDS
)
DEFAULT_MAZE_WIDTH = 23
DEFAULT_MAZE_HEIGHT = 17
_VECTORS: tuple[Vector, ...] = ((0, -1), (1, 0), (0, 1), (-1, 0))


class Direction(IntEnum):
    """Cardinal direction, increasing clockwise."""

    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3


class Action(Enum):
    """A discrete player command."""

    FORWARD = "forward"
    BACKWARD = "backward"
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"


@dataclass(frozen=True, slots=True)
class Maze:
    """A rectangular maze whose cells are walls, floor, or the exit."""

    rows: tuple[str, ...]
    exit_position: Point
    entry_position: Point = (1, 1)
    entry_facing: Direction = Direction.EAST

    def __post_init__(self) -> None:
        if not self.rows or not self.rows[0]:
            raise ValueError("maze rows must not be empty")
        width = len(self.rows[0])
        if any(len(row) != width for row in self.rows):
            raise ValueError("maze rows must have equal width")
        if any(set(row) - {"#", ".", "E"} for row in self.rows):
            raise ValueError("maze cells must be '#', '.', or 'E'")
        exits = [
            (x, y)
            for y, row in enumerate(self.rows)
            for x, tile in enumerate(row)
            if tile == "E"
        ]
        if exits != [self.exit_position]:
            raise ValueError(
                "exit_position must identify the maze's only exit"
            )
        entry_x, entry_y = self.entry_position
        if (
            entry_x < 0
            or entry_y < 0
            or entry_x >= width
            or entry_y >= len(self.rows)
            or self.rows[entry_y][entry_x] != "."
        ):
            raise ValueError("entry_position must identify a floor cell")

    @property
    def width(self) -> int:
        """Return the number of columns."""

        return len(self.rows[0])

    @property
    def height(self) -> int:
        """Return the number of rows."""

        return len(self.rows)

    def tile(self, position: Point) -> str:
        """Return a cell; out-of-bounds positions behave as walls."""

        x, y = position
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return "#"
        return self.rows[y][x]


@dataclass(frozen=True, slots=True)
class Animation:
    """An in-progress action, advanced one display frame at a time."""

    action: Action
    frame: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.frame < ANIMATION_STEPS:
            raise ValueError("animation frame is outside its eight steps")


@dataclass(frozen=True, slots=True)
class GameState:
    """Complete immutable state required to render and advance a game."""

    position: Point
    facing: Direction
    explored: frozenset[Point]
    animation: Animation | None = None
    solved: bool = False
    solution_elapsed: float | None = None


def direction_vector(direction: Direction) -> Vector:
    """Return the grid movement vector for a cardinal direction."""

    return _VECTORS[int(direction)]


def step(position: Point, direction: Direction, distance: int = 1) -> Point:
    """Move a point along a cardinal direction."""

    dx, dy = direction_vector(direction)
    return position[0] + dx * distance, position[1] + dy * distance


def visible_cells(
    maze: Maze,
    position: Point,
    facing: Direction,
    depth: int = VIEW_DEPTH,
) -> frozenset[Point]:
    """Return cells visible down a corridor and through side openings."""

    visible = {position}
    left = direction_vector(Direction((int(facing) - 1) % 4))
    right = direction_vector(Direction((int(facing) + 1) % 4))
    for distance in range(1, depth + 1):
        center = step(position, facing, distance)
        visible.add(center)
        for side in (left, right):
            side_cell = center[0] + side[0], center[1] + side[1]
            visible.add(side_cell)
        if maze.tile(center) != ".":
            break
    return frozenset(visible)


def initial_state(
    maze: Maze,
    position: Point | None = None,
    facing: Direction | None = None,
) -> GameState:
    """Create a new state and reveal the starting view."""

    position = maze.entry_position if position is None else position
    facing = maze.entry_facing if facing is None else facing
    if maze.tile(position) != ".":
        raise ValueError("starting position must be a floor cell")
    return GameState(
        position=position,
        facing=facing,
        explored=visible_cells(maze, position, facing),
    )


def begin_action(state: GameState, maze: Maze, action: Action) -> GameState:
    """Start an action unless the game is busy, solved, or blocked."""

    if state.solved or state.animation is not None:
        return state
    if action in (Action.FORWARD, Action.BACKWARD):
        distance = 1 if action is Action.FORWARD else -1
        destination = step(state.position, state.facing, distance)
        if maze.tile(destination) == "#":
            return state
    return replace(state, animation=Animation(action))


def advance_animation(state: GameState, maze: Maze) -> GameState:
    """Advance one frame and commit completed actions atomically."""

    animation = state.animation
    if animation is None or state.solved:
        return state
    if animation.frame < ANIMATION_STEPS - 1:
        return replace(
            state, animation=replace(animation, frame=animation.frame + 1)
        )

    action = animation.action
    position = state.position
    facing = state.facing
    solved: bool = state.solved
    if action is Action.FORWARD:
        destination = step(position, facing)
        if destination == maze.exit_position:
            solved = True
        else:
            position = destination
    elif action is Action.BACKWARD:
        destination = step(position, facing, -1)
        if destination == maze.exit_position:
            solved = True
        else:
            position = destination
    elif action is Action.TURN_LEFT:
        facing = Direction((int(facing) - 1) % 4)
    else:
        facing = Direction((int(facing) + 1) % 4)

    return GameState(
        position=position,
        facing=facing,
        explored=state.explored | visible_cells(maze, position, facing),
        solved=solved,
        solution_elapsed=(
            0.0 if solved and not state.solved else state.solution_elapsed
        ),
    )


def advance_solution_timer(
    state: GameState, delta_seconds: float
) -> GameState:
    """Advance the win countdown, clamped to its five-second duration."""

    if not state.solved:
        return state
    elapsed = state.solution_elapsed or 0.0
    updated_elapsed = min(
        SOLUTION_COUNTDOWN_DURATION,
        elapsed + max(0.0, delta_seconds),
    )
    if updated_elapsed == state.solution_elapsed:
        return state
    return replace(state, solution_elapsed=updated_elapsed)


def solution_countdown(state: GameState) -> int | None:
    """Return the visible countdown value, or None when it has completed."""

    if not state.solved:
        return None
    elapsed = state.solution_elapsed or 0.0
    remaining = SOLUTION_COUNTDOWN_STEPS - int(
        elapsed / SOLUTION_COUNTDOWN_STEP_SECONDS
    )
    return remaining if remaining > 0 else None


def view_pose(state: GameState) -> tuple[float, float, float]:
    """Return the interpolated camera center and heading in radians."""

    x, y = state.position
    center_x = x + 0.5
    center_y = y + 0.5
    heading = (int(state.facing) * pi / 2) - pi / 2
    animation = state.animation
    if animation is None:
        return center_x, center_y, heading

    progress = animation.frame / ANIMATION_STEPS
    if animation.action in (Action.FORWARD, Action.BACKWARD):
        distance = 1 if animation.action is Action.FORWARD else -1
        dx, dy = direction_vector(state.facing)
        return (
            center_x + dx * distance * progress,
            center_y + dy * distance * progress,
            heading,
        )

    turn = -1 if animation.action is Action.TURN_LEFT else 1
    return center_x, center_y, heading + (turn * pi / 2) * progress


def _unvisited_neighbors(
    position: Point,
    width: int,
    height: int,
    visited: set[Point],
) -> list[Point]:
    x, y = position
    return [
        (x + dx * 2, y + dy * 2)
        for dx, dy in _VECTORS
        if 1 <= x + dx * 2 < width - 1
        and 1 <= y + dy * 2 < height - 1
        and (x + dx * 2, y + dy * 2) not in visited
    ]


def _carve_passages(width: int, height: int, rng: Random) -> list[list[str]]:
    grid = [["#"] * width for _ in range(height)]
    start = (
        rng.choice(range(1, width - 1, 2)),
        rng.choice(range(1, height - 1, 2)),
    )
    grid[start[1]][start[0]] = "."
    visited: set[Point] = {start}
    stack: list[Point] = [start]

    while stack:
        position = stack[-1]
        neighbors = _unvisited_neighbors(position, width, height, visited)
        if not neighbors:
            stack.pop()
            continue
        rng.shuffle(neighbors)
        next_cell = neighbors[0]
        wall = (
            (position[0] + next_cell[0]) // 2,
            (position[1] + next_cell[1]) // 2,
        )
        grid[wall[1]][wall[0]] = "."
        grid[next_cell[1]][next_cell[0]] = "."
        visited.add(next_cell)
        stack.append(next_cell)
    return grid


def _wall_panels(grid: list[list[str]]) -> list[Point]:
    height = len(grid)
    width = len(grid[0])
    candidates = [
        (x, y)
        for y in range(1, height - 1)
        for x in range(1, width - 1)
        if grid[y][x] == "#"
        and any(grid[y + dy][x + dx] == "." for dx, dy in _VECTORS)
    ]
    return candidates


def generate_maze(
    width: int = DEFAULT_MAZE_WIDTH,
    height: int = DEFAULT_MAZE_HEIGHT,
    seed: int | None = None,
) -> Maze:
    """Generate a connected randomized maze with a reachable wall exit.

    Supplying a seed makes generation reproducible. Width and height must be
    odd and at least seven so the start and maze passages fit the grid.
    """

    if width < 7 or height < 7 or width % 2 == 0 or height % 2 == 0:
        raise ValueError("maze dimensions must be odd integers of at least 7")
    rng = Random(seed)
    grid = _carve_passages(width, height, rng)
    floor_cells = [
        (x, y)
        for y, row in enumerate(grid)
        for x, tile in enumerate(row)
        if tile == "."
    ]
    entry_position = rng.choice(floor_cells)
    exit_position = rng.choice(_wall_panels(grid))
    grid[exit_position[1]][exit_position[0]] = "E"
    entry_directions = [
        direction
        for direction in Direction
        if grid[entry_position[1] + direction_vector(direction)[1]][
            entry_position[0] + direction_vector(direction)[0]
        ]
        == "."
    ]
    entry_facing = rng.choice(entry_directions)
    return Maze(
        tuple("".join(row) for row in grid),
        exit_position,
        entry_position,
        entry_facing,
    )
