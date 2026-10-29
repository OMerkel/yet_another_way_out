"""Pygame drawing and grid-based first-person ray casting."""

from __future__ import annotations

from math import atan, cos, floor, pi, sin, tan, tau
from typing import NamedTuple

import pygame

from .model import (
    VIEW_DEPTH,
    Direction,
    GameState,
    Maze,
    direction_vector,
    solution_countdown,
    view_pose,
    visible_cells,
)

SCREEN_SIZE = (1100, 760)
_FIELD_OF_VIEW = pi / 3
_RAY_STRIDE = 4
_MAP_COLUMNS = 11
_MAP_ROWS = 9
_SKY = (29, 42, 49)
_FLOOR = (38, 43, 42)


class RayHit(NamedTuple):
    """The first opaque cell touched by a camera ray."""

    cell: tuple[int, int]
    distance: float
    side: int
    is_exit: bool


class _GridRay(NamedTuple):
    cell: tuple[int, int]
    step: tuple[int, int]
    delta: tuple[float, float]
    side_distance: tuple[float, float]


class _MapLayout(NamedTuple):
    cell_size: int
    origin_x: int
    origin_y: int
    map_width: int
    map_height: int
    columns: int
    rows: int


class _Camera(NamedTuple):
    origin: tuple[float, float]
    heading: float
    width: int
    height: int
    horizon: int


def _grid_ray(origin: tuple[float, float], angle: float) -> _GridRay:
    origin_x, origin_y = origin
    ray_x = cos(angle)
    ray_y = sin(angle)
    cell_x = floor(origin_x)
    cell_y = floor(origin_y)
    step_x = 1 if ray_x >= 0 else -1
    step_y = 1 if ray_y >= 0 else -1
    delta_x = abs(1 / ray_x) if ray_x else float("inf")
    delta_y = abs(1 / ray_y) if ray_y else float("inf")
    side_x = (
        (cell_x + 1 - origin_x) * delta_x
        if step_x > 0
        else (origin_x - cell_x) * delta_x
    )
    side_y = (
        (cell_y + 1 - origin_y) * delta_y
        if step_y > 0
        else (origin_y - cell_y) * delta_y
    )
    return _GridRay(
        (cell_x, cell_y),
        (step_x, step_y),
        (delta_x, delta_y),
        (side_x, side_y),
    )


def _advance_ray(ray: _GridRay) -> tuple[_GridRay, float, int]:
    cell_x, cell_y = ray.cell
    step_x, step_y = ray.step
    delta_x, delta_y = ray.delta
    side_x, side_y = ray.side_distance
    if side_x < side_y:
        return (
            _GridRay(
                (cell_x + step_x, cell_y),
                ray.step,
                ray.delta,
                (side_x + delta_x, side_y),
            ),
            side_x,
            0,
        )
    return (
        _GridRay(
            (cell_x, cell_y + step_y),
            ray.step,
            ray.delta,
            (side_x, side_y + delta_y),
        ),
        side_y,
        1,
    )


def cast_ray(
    maze: Maze,
    origin: tuple[float, float],
    angle: float,
    max_distance: float = float(VIEW_DEPTH),
) -> RayHit | None:
    """Find the first wall or exit along a ray using grid DDA."""

    ray = _grid_ray(origin, angle)
    while min(ray.side_distance) <= max_distance:
        ray, distance, side = _advance_ray(ray)
        tile = maze.tile(ray.cell)
        if tile in ("#", "E"):
            return RayHit(ray.cell, distance, side, tile == "E")
    return None


def _map_cell_color(
    tile: str,
    position: tuple[int, int],
    visible: frozenset[tuple[int, int]],
) -> tuple[int, int, int]:
    if tile == "#":
        return 72, 83, 82
    if tile == "E":
        return 83, 235, 190
    if position in visible:
        return 225, 218, 191
    return 133, 149, 143


def _ego_map_cell(
    position: tuple[int, int],
    state: GameState,
    layout: _MapLayout,
) -> tuple[int, int]:
    world_x = position[0] - state.position[0]
    world_y = position[1] - state.position[1]
    forward_x, forward_y = direction_vector(state.facing)
    right_x, right_y = direction_vector(Direction((int(state.facing) + 1) % 4))
    map_x = layout.columns // 2 + world_x * right_x + world_y * right_y
    map_y = layout.rows // 2 - world_x * forward_x - world_y * forward_y
    return map_x, map_y


def _draw_map_cells(
    surface: pygame.Surface,
    maze: Maze,
    state: GameState,
    layout: _MapLayout,
    visible: frozenset[tuple[int, int]],
) -> None:
    for x, y in state.explored:
        map_x, map_y = _ego_map_cell((x, y), state, layout)
        if not (0 <= map_x < layout.columns and 0 <= map_y < layout.rows):
            continue
        color = _map_cell_color(maze.tile((x, y)), (x, y), visible)
        pygame.draw.rect(
            surface,
            color,
            (
                layout.origin_x + map_x * layout.cell_size,
                layout.origin_y + map_y * layout.cell_size,
                layout.cell_size - 1,
                layout.cell_size - 1,
            ),
        )


def _draw_player_marker(
    surface: pygame.Surface,
    layout: _MapLayout,
) -> None:
    center_x = layout.origin_x + (layout.columns // 2 + 0.5) * layout.cell_size
    center_y = layout.origin_y + (layout.rows // 2 + 0.5) * layout.cell_size
    pygame.draw.line(
        surface,
        (239, 101, 80),
        (round(center_x), round(center_y)),
        (
            round(center_x),
            round(center_y - layout.cell_size * 0.8),
        ),
        2,
    )
    pygame.draw.circle(
        surface,
        (248, 111, 84),
        (round(center_x), round(center_y)),
        max(2, layout.cell_size // 3),
    )


def draw_minimap(
    surface: pygame.Surface,
    maze: Maze,
    state: GameState,
) -> None:
    """Draw an ego-centered, forward-up view of explored cells."""

    width, _ = surface.get_size()
    cell_size = max(4, min(11, (width - 30) // _MAP_COLUMNS))
    map_width = _MAP_COLUMNS * cell_size
    map_height = _MAP_ROWS * cell_size
    origin_x = (width - map_width) // 2
    origin_y = 18
    panel = pygame.Rect(
        origin_x - 8,
        origin_y - 8,
        map_width + 16,
        map_height + 16,
    )
    pygame.draw.rect(surface, (8, 15, 18), panel, border_radius=3)
    pygame.draw.rect(surface, (113, 139, 137), panel, 1, border_radius=3)
    visible = visible_cells(maze, state.position, state.facing)
    layout = _MapLayout(
        cell_size,
        origin_x,
        origin_y,
        map_width,
        map_height,
        _MAP_COLUMNS,
        _MAP_ROWS,
    )
    _draw_map_cells(surface, maze, state, layout, visible)
    _draw_player_marker(surface, layout)


def plasma_color(u: float, v: float, elapsed: float) -> tuple[int, int, int]:
    """Return a wavy plasma color at normalized panel coordinates."""

    horizontal_wave = sin(
        tau
        * (
            u * 2.4
            + 0.13 * sin(tau * (v * 1.5 + elapsed * 0.18))
            + elapsed * 0.22
        )
    )
    vertical_wave = sin(
        tau
        * (
            v * 2.8
            + 0.16 * sin(tau * (u * 1.8 - elapsed * 0.16))
            - elapsed * 0.18
        )
    )
    diagonal_wave = sin(tau * ((u + v) * 1.8 + elapsed * 0.12))
    hue = (
        176 + 52 * horizontal_wave + 48 * vertical_wave + 28 * diagonal_wave
    ) % 360
    saturation = 86 + 12 * sin(tau * (u - v + elapsed * 0.1))
    value = 74 + 22 * sin(tau * (horizontal_wave + vertical_wave) * 0.25)
    color = pygame.Color(0)
    color.hsva = (hue, saturation, value, 100)
    return color.r, color.g, color.b


def _wall_color(hit: RayHit) -> tuple[int, int, int]:
    brightness = max(0.20, 1 - hit.distance / (VIEW_DEPTH + 1))
    if hit.side:
        brightness *= 0.72
    panel_edge = hit.distance % 1 < 0.045
    if panel_edge:
        brightness *= 0.62
    return (
        round(105 * brightness),
        round(119 * brightness),
        round(112 * brightness),
    )


def _draw_plasma_panel(
    surface: pygame.Surface,
    panel: pygame.Rect,
    elapsed: float,
) -> None:
    panel_width = max(1, panel.width)
    panel_height = max(1, panel.height)
    u = panel.centerx / surface.get_width()
    for y in range(panel.top, panel.bottom, 4):
        v = (y - panel.top) / panel_height
        color = plasma_color(u, v, elapsed)
        segment_height = min(4, panel.bottom - y)
        pygame.draw.rect(
            surface,
            color,
            (panel.left, y, panel_width, segment_height),
        )


def _draw_backdrop(
    surface: pygame.Surface,
) -> int:
    width, height = surface.get_size()
    horizon = int(height * 0.43)
    surface.fill(_SKY)
    pygame.draw.rect(surface, _FLOOR, (0, horizon, width, height - horizon))
    for depth in range(1, VIEW_DEPTH + 1):
        line_y = horizon + int((height - horizon) * depth / (depth + 4))
        pygame.draw.line(surface, (57, 61, 56), (0, line_y), (width, line_y))
    return horizon


def _camera(surface: pygame.Surface, state: GameState) -> _Camera:
    width, height = surface.get_size()
    origin_x, origin_y, heading = view_pose(state)
    return _Camera(
        (origin_x, origin_y), heading, width, height, int(height * 0.43)
    )


def _draw_ray_column(
    surface: pygame.Surface,
    maze: Maze,
    camera: _Camera,
    elapsed: float,
    screen_x: int,
) -> None:
    camera_x = (2 * (screen_x + _RAY_STRIDE / 2) / camera.width) - 1
    ray_angle = camera.heading + atan(camera_x * tan(_FIELD_OF_VIEW / 2))
    hit = cast_ray(maze, camera.origin, ray_angle)
    if hit is None:
        return
    corrected_distance = max(
        0.12, hit.distance * cos(ray_angle - camera.heading)
    )
    wall_height = min(
        camera.height, int(camera.height * 0.9 / corrected_distance)
    )
    top = max(0, camera.horizon - wall_height // 2)
    bottom = min(camera.height, top + wall_height)
    wall = pygame.Rect(screen_x, top, _RAY_STRIDE + 1, bottom - top)
    if hit.is_exit:
        _draw_plasma_panel(surface, wall, elapsed)
    else:
        pygame.draw.rect(surface, _wall_color(hit), wall)


def _draw_walls(
    surface: pygame.Surface,
    maze: Maze,
    camera: _Camera,
    elapsed: float,
) -> None:
    for screen_x in range(0, camera.width, _RAY_STRIDE):
        _draw_ray_column(surface, maze, camera, elapsed, screen_x)


def _draw_status(
    surface: pygame.Surface,
    state: GameState,
    width: int,
    height: int,
) -> None:
    font = pygame.font.SysFont("consolas", 16)
    caption = "W/S or arrows: move    A/D or arrows: turn"
    text = font.render(caption, True, (213, 219, 207))
    surface.blit(text, (16, height - text.get_height() - 13))
    if state.solved:
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((8, 20, 20, 150))
        surface.blit(overlay, (0, 0))
        message = pygame.font.SysFont("consolas", 34, bold=True).render(
            "WAY OUT FOUND", True, (130, 255, 215)
        )
        surface.blit(
            message,
            (
                (width - message.get_width()) // 2,
                height // 2 - message.get_height(),
            ),
        )
        countdown = solution_countdown(state)
        if countdown is None:
            prompt = pygame.font.SysFont("consolas", 18).render(
                "PRESS ANY KEY OR GAMEPAD BUTTON TO START A NEW GAME",
                True,
                (231, 234, 219),
            )
            surface.blit(
                prompt,
                (
                    (width - prompt.get_width()) // 2,
                    height // 2 + 8,
                ),
            )
        else:
            numeral = pygame.font.SysFont("consolas", 88, bold=True).render(
                str(countdown), True, (83, 235, 190)
            )
            surface.blit(
                numeral,
                (
                    (width - numeral.get_width()) // 2,
                    height // 2 + 8,
                ),
            )


def draw_scene(
    surface: pygame.Surface,
    maze: Maze,
    state: GameState,
    elapsed: float = 0.0,
) -> None:
    """Draw the animated first-person view and exploration map."""

    camera = _camera(surface, state)
    _draw_backdrop(surface)
    _draw_walls(surface, maze, camera, elapsed)
    draw_minimap(surface, maze, state)
    _draw_status(surface, state, camera.width, camera.height)
