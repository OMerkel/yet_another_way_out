"""Headless tests for ray casting and pygame drawing."""

import os
from collections.abc import Generator
from dataclasses import replace
from math import pi

import pygame
import pytest

from way_out_game.model import (
    SOLUTION_COUNTDOWN_DURATION,
    Action,
    Direction,
    Maze,
    advance_animation,
    begin_action,
    initial_state,
)
from way_out_game.rendering import (
    cast_ray,
    draw_minimap,
    draw_scene,
    plasma_color,
)


@pytest.fixture(scope="module", autouse=True)
def pygame_init() -> Generator[None]:
    """Initialize pygame with headless drivers for rendering tests."""

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    yield
    pygame.quit()


def test_ray_hits_wall_at_known_distance(maze: Maze) -> None:
    """FR-REN-001
    Feature: First-person ray casting
    Scenario: A ray reports its first wall hit and distance
    GIVEN a ray facing a known wall
    WHEN the ray is cast
    THEN the first cell, distance, and wall classification are returned
    """

    hit = cast_ray(maze, (1.5, 1.5), -pi / 2)
    assert hit is not None
    assert hit.cell == (1, 0)
    assert hit.distance == pytest.approx(0.5)
    assert not hit.is_exit


def test_ray_hits_exit_panel(maze: Maze) -> None:
    """FR-REN-001
    Feature: First-person ray casting
    Scenario: A ray identifies the exit panel
    GIVEN a ray directed at the exit panel
    WHEN the ray is cast
    THEN the first hit is marked as an exit
    """

    hit = cast_ray(maze, (13.5, 8.5), pi / 2)
    assert hit is not None
    assert hit.cell == (13, 9)
    assert hit.is_exit


def test_ray_returns_none_past_short_range(maze: Maze) -> None:
    """FR-REN-001
    Feature: First-person ray casting
    Scenario: A ray returns no hit beyond its maximum range
    GIVEN a maximum ray distance ending before a wall
    WHEN the ray is cast
    THEN no hit is returned
    """

    assert cast_ray(maze, (1.5, 1.5), 0.0, 0.25) is None


def test_ray_handles_zero_components(maze: Maze) -> None:
    """FR-REN-001
    Feature: First-person ray casting
    Scenario: Cardinal rays handle a zero direction component
    GIVEN a ray aligned with either grid axis
    WHEN the ray is cast
    THEN traversal completes and finds the expected obstruction
    """

    assert cast_ray(maze, (1.5, 1.5), 0.0) is not None
    assert cast_ray(maze, (1.5, 1.5), pi / 2) is not None


def test_plasma_color_varies_across_both_axes_and_time() -> None:
    """FR-REN-003
    Feature: Animated exit presentation
    Scenario: Exit plasma varies across the panel and time
    GIVEN normalized panel coordinates and elapsed time
    WHEN the plasma color is calculated
    THEN horizontal, vertical, and temporal changes affect the color
    """

    origin = plasma_color(0.3, 0.4, 1.0)
    assert plasma_color(0.8, 0.4, 1.0) != origin
    assert plasma_color(0.3, 0.9, 1.0) != origin
    assert plasma_color(0.3, 0.4, 2.5) != origin


def test_minimap_draws_to_surface(maze: Maze) -> None:
    """FR-REN-002
    Feature: Ego-centered exploration map
    Scenario: The minimap is drawn to the scene surface
    GIVEN a maze and initial game state
    WHEN the minimap is drawn
    THEN visible map pixels are written to the surface
    """

    surface = pygame.Surface((500, 300))
    draw_minimap(surface, maze, initial_state(maze))
    assert surface.get_at((250, 18)).a == 255


def test_minimap_draws_explored_floor_outside_current_view(
    maze: Maze,
) -> None:
    """FR-REN-002
    Feature: Ego-centered exploration map
    Scenario: Previously explored floor remains visible on the map
    GIVEN an explored floor cell outside the current view
    WHEN the minimap is drawn
    THEN that cell uses the explored, non-currently-visible color
    """

    state = initial_state(maze, (1, 1), Direction.EAST)
    state = replace(state, explored=state.explored | {(1, 2)})
    surface = pygame.Surface((500, 300))
    draw_minimap(surface, maze, state)
    assert surface.get_at((256, 63)) == pygame.Color(133, 149, 143)


def test_minimap_centers_player_and_keeps_forward_up(maze: Maze) -> None:
    """FR-REN-002
    Feature: Ego-centered exploration map
    Scenario: The player stays centered and forward stays up
    GIVEN player positions and each cardinal facing
    WHEN the minimap is drawn
    THEN the player marker remains centered with its heading upward
    """

    surface = pygame.Surface((500, 300))
    player_color = pygame.Color(248, 111, 84)
    heading_color = pygame.Color(239, 101, 80)
    for position, facing in (
        ((1, 1), Direction.EAST),
        ((2, 1), Direction.NORTH),
        ((5, 1), Direction.WEST),
        ((5, 1), Direction.SOUTH),
    ):
        surface.fill((0, 0, 0))
        draw_minimap(surface, maze, initial_state(maze, position, facing))
        assert surface.get_at((250, 68)) == player_color
        assert surface.get_at((250, 60)) == heading_color


def test_scene_draws_and_animates_exit(maze: Maze) -> None:
    """FR-REN-003
    Feature: First-person scene
    Scenario: The scene renders a visible animated exit
    GIVEN a player looking toward the exit
    WHEN the scene is drawn at an elapsed time
    THEN the first-person surface includes the exit presentation
    """

    state = initial_state(maze, (13, 8), Direction.SOUTH)
    surface = pygame.Surface((320, 240))
    draw_scene(surface, maze, state, elapsed=1.5)
    assert surface.get_at((160, 120)) != pygame.Color(0, 0, 0, 255)


def test_scene_handles_rays_with_no_hit_in_view_range() -> None:
    """FR-REN-003
    Feature: First-person scene
    Scenario: Open rays do not prevent scene rendering
    GIVEN an open corridor with walls beyond the ray range
    WHEN the scene is drawn
    THEN rendering completes on the requested surface
    """

    width = 25
    height = 25
    rows = ["#" * width]
    rows.extend("#" + "." * (width - 2) + "#" for _ in range(height - 2))
    rows.append("#" * width)
    rows[12] = rows[12][:-1] + "E"
    maze = Maze(
        rows=tuple(rows),
        exit_position=(width - 1, 12),
        entry_position=(12, 12),
        entry_facing=Direction.NORTH,
    )
    surface = pygame.Surface((320, 240))
    draw_scene(surface, maze, initial_state(maze))
    assert surface.get_size() == (320, 240)


def test_scene_draws_solved_overlay(maze: Maze) -> None:
    """FR-REN-003
    Feature: Victory presentation
    Scenario: A solved scene displays the countdown overlay
    GIVEN a completed maze before countdown expiry
    WHEN the scene is drawn
    THEN a solved overlay and countdown numeral are visible
    """

    state = initial_state(maze, (13, 8), Direction.SOUTH)
    state = begin_action(state, maze, Action.FORWARD)
    for _ in range(8):
        state = advance_animation(state, maze)
    surface = pygame.Surface((320, 240))
    draw_scene(surface, maze, state)
    assert state.solved
    assert surface.get_at((160, 120)).a == 255
    countdown_color = pygame.Color(83, 235, 190)
    assert any(
        surface.get_at((x, y)) == countdown_color
        for x in range(surface.get_width())
        for y in range(surface.get_height() // 2, surface.get_height())
    )


def test_scene_offers_restart_after_countdown(maze: Maze) -> None:
    """FR-REN-003
    Feature: Victory presentation
    Scenario: A completed countdown displays the restart prompt
    GIVEN a solved state at the full countdown duration
    WHEN the scene is drawn
    THEN the restart prompt is visible
    """

    state = initial_state(maze, (13, 8), Direction.SOUTH)
    state = begin_action(state, maze, Action.FORWARD)
    for _ in range(8):
        state = advance_animation(state, maze)
    state = replace(
        state,
        solution_elapsed=SOLUTION_COUNTDOWN_DURATION,
    )
    surface = pygame.Surface((500, 300))
    draw_scene(surface, maze, state)
    prompt_color = pygame.Color(231, 234, 219)
    assert any(
        surface.get_at((x, y)) == prompt_color
        for x in range(surface.get_width())
        for y in range(surface.get_height() // 2, surface.get_height())
    )
