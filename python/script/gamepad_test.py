#!/usr/bin/env python3
"""Display live gamepad input on a pygame controller silhouette.

Run from the repository root with:
    uv run --project python python/script/gamepad_test.py

Escape closes the window; Tab switches between connected gamepads.
The silhouette uses a common raw joystick layout, not a device-specific
mapping. Numbered readouts show every axis, button, and hat on any device.
Device setup and raw input are shared with the game in way_out_game.gamepad.
"""

from __future__ import annotations

import pygame

from way_out_game.gamepad import (
    LEFT_STICK_AXES,
    RIGHT_STICK_AXES,
    Gamepads,
    GamepadState,
)

BACKGROUND = (22, 25, 32)
BODY = (64, 71, 86)
IDLE = (36, 41, 52)
ACTIVE = (70, 220, 150)
TEXT = (235, 239, 245)
MUTED = (155, 166, 185)
DEADZONE = 0.15
WIDTH = 1000


def draw_text(
    screen: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    position: tuple[int, int],
    color: tuple[int, int, int] = TEXT,
) -> None:
    """Draw a single line of text."""

    screen.blit(font.render(text, True, color), position)


def draw_stick(
    screen: pygame.Surface,
    font: pygame.font.Font,
    state: GamepadState,
    axis: int,
    center: tuple[int, int],
) -> None:
    """Draw a stick's displacement and click state."""

    button = (7, 8)[axis // 2]
    x_value, y_value = state.axis(axis), state.axis(axis + 1)
    active = max(abs(x_value), abs(y_value)) > DEADZONE or state.pressed(
        button
    )
    pygame.draw.circle(screen, IDLE, center, 43)
    pygame.draw.circle(
        screen,
        ACTIVE if active else MUTED,
        (center[0] + round(x_value * 22), center[1] + round(y_value * 22)),
        20,
    )
    draw_text(
        screen,
        font,
        f"A{axis}/{axis + 1} B{button}",
        (center[0] - 50, center[1] + 47),
    )


def draw_silhouette(
    screen: pygame.Surface,
    font: pygame.font.Font,
    state: GamepadState,
    resting_axes: list[float],
) -> None:
    """Draw a common raw joystick layout on a controller silhouette."""

    pygame.draw.polygon(
        screen,
        BODY,
        [
            (100, 145),
            (215, 110),
            (425, 110),
            (540, 145),
            (605, 340),
            (580, 390),
            (520, 390),
            (425, 310),
            (215, 310),
            (120, 390),
            (60, 390),
            (35, 340),
        ],
    )
    for index, position in (
        (0, (495, 252)),
        (1, (530, 217)),
        (2, (460, 217)),
        (3, (495, 182)),
        (9, (150, 125)),
        (10, (490, 125)),
        (4, (200, 145)),
        (6, (440, 145)),
        (15, (320, 165)),
        (5, (320, 280)),
    ):
        if index == 15:
            pygame.draw.rect(
                screen,
                ACTIVE if state.pressed(index) else IDLE,
                (position[0] - 90, position[1] - 45, 180, 90),
            )
        else:
            pygame.draw.circle(
                screen, ACTIVE if state.pressed(index) else IDLE, position, 19
            )
        label = font.render(f"B{index}", True, TEXT)
        screen.blit(label, label.get_rect(center=position))

    draw_stick(screen, font, state, LEFT_STICK_AXES[0], (235, 280))
    draw_stick(screen, font, state, RIGHT_STICK_AXES[0], (405, 280))

    hat_x, hat_y = state.hats[0] if state.hats else (0, 0)
    for dx, dy, button in ((0, 1, 11), (-1, 0, 13), (0, -1, 12), (1, 0, 14)):
        active = (
            (dx != 0 and dx == hat_x)
            or (dy != 0 and dy == hat_y)
            or state.pressed(button)
        )
        pygame.draw.rect(
            screen,
            ACTIVE if active else IDLE,
            (133 + dx * 23, 218 - dy * 23, 22, 22),
            border_radius=4,
        )
    draw_text(screen, font, "H0 / B11-14", (95, 275))

    for axis, x_position in ((4, 115), (5, 455)):
        active = (
            axis < len(state.axes)
            and abs(state.axes[axis] - resting_axes[axis]) > DEADZONE
        )
        pygame.draw.rect(
            screen,
            ACTIVE if active else IDLE,
            (x_position, 82, 70, 22),
            border_radius=8,
        )
        draw_text(screen, font, f"A{axis}", (x_position + 20, 84))


def draw_raw_controls(
    screen: pygame.Surface,
    font: pygame.font.Font,
    state: GamepadState,
    resting_axes: list[float],
) -> None:
    """Show every input, including controls outside the silhouette."""

    draw_text(screen, font, "Raw controls", (660, 82))
    for index, value in enumerate(state.axes):
        y_position = 116 + index * 30
        reference = resting_axes[index] if index >= 4 else 0.0
        active = abs(value - reference) > DEADZONE
        draw_text(
            screen,
            font,
            f"A{index}: {value:+.3f}",
            (660, y_position),
            ACTIVE if active else TEXT,
        )
        pygame.draw.rect(screen, BODY, (815, y_position + 5, 160, 12))
        pygame.draw.line(
            screen, MUTED, (895, y_position + 2), (895, y_position + 19)
        )
        pygame.draw.circle(
            screen,
            ACTIVE if active else MUTED,
            (895 + round(value * 77), y_position + 11),
            5,
        )

    button_y = max(425, 130 + len(state.axes) * 30)
    draw_text(screen, font, "Buttons", (24, button_y))
    for index, pressed in enumerate(state.buttons):
        x_position = 24 + index % 20 * 48
        y_position = button_y + 30 + index // 20 * 32
        pygame.draw.rect(
            screen,
            ACTIVE if pressed else IDLE,
            (x_position, y_position, 42, 26),
            border_radius=5,
        )
        draw_text(
            screen,
            font,
            str(index),
            (x_position + 7, y_position + 3),
            BACKGROUND if pressed else TEXT,
        )

    hat_y_position = button_y + 40 + ((len(state.buttons) + 19) // 20) * 32
    for index, hat in enumerate(state.hats):
        draw_text(
            screen,
            font,
            f"H{index}: {hat}",
            (24, hat_y_position + index * 26),
            ACTIVE if hat != (0, 0) else TEXT,
        )


def draw_gamepad(
    screen: pygame.Surface,
    font: pygame.font.Font,
    state: GamepadState,
    resting_axes: list[float],
) -> None:
    """Draw the silhouette and complete raw control readouts."""

    screen.fill(BACKGROUND)
    draw_text(screen, font, state.name, (24, 18))
    draw_text(screen, font, "Tab: next gamepad    Esc: quit", (24, 46), MUTED)
    draw_silhouette(screen, font, state, resting_axes)
    draw_raw_controls(screen, font, state, resting_axes)
    draw_text(
        screen,
        font,
        "Raw layout varies by device; A = axis, B = button, H = hat.",
        (24, screen.get_height() - 30),
        MUTED,
    )


def handle_event(
    event: pygame.event.Event,
    gamepads: Gamepads,
    selected: int | None,
) -> tuple[int | None, bool]:
    """Handle connection changes, selection, and window exit requests."""

    if event.type == pygame.QUIT:
        return selected, False
    if event.type == pygame.KEYDOWN:
        if event.key == pygame.K_ESCAPE:
            return selected, False
        if event.key == pygame.K_TAB and gamepads.devices:
            ids = list(gamepads.devices)
            selected = (
                ids[(ids.index(selected) + 1) % len(ids)]
                if selected is not None and selected in ids
                else ids[0]
            )
    gamepads.handle_event(event)
    return selected, True


def run_gamepad_test(max_frames: int | None = None) -> None:
    """Run the visualizer, optionally limiting frames for automated tests."""

    pygame.init()
    gamepads = Gamepads()
    selected: int | None = None
    try:
        screen = pygame.display.set_mode((WIDTH, 620))
        pygame.display.set_caption("Gamepad input test")
        font = pygame.font.Font(None, 24)
        clock = pygame.time.Clock()
        gamepads.open_connected()
        frame_count = 0
        running = True
        while running and (max_frames is None or frame_count < max_frames):
            for event in pygame.event.get():
                selected, running = handle_event(event, gamepads, selected)
                if not running:
                    break
            if not running:
                break
            if selected not in gamepads.devices:
                selected = next(iter(gamepads.devices), None)
            if selected is None:
                screen.fill(BACKGROUND)
                draw_silhouette(screen, font, GamepadState("", [], [], []), [])
                draw_text(
                    screen, font, "Connect a gamepad to begin.", (24, 24)
                )
                draw_text(screen, font, "Esc: quit", (24, 56), MUTED)
            else:
                state = GamepadState.read(gamepads.devices[selected])
                button_y = max(425, 130 + len(state.axes) * 30)
                height = max(
                    620,
                    button_y
                    + 90
                    + ((len(state.buttons) + 19) // 20) * 32
                    + len(state.hats) * 26,
                )
                if screen.get_height() != height:
                    screen = pygame.display.set_mode((WIDTH, height))
                draw_gamepad(
                    screen, font, state, gamepads.resting_axes[selected]
                )
            pygame.display.flip()
            clock.tick(60)
            frame_count += 1
    finally:
        gamepads.close()
        pygame.quit()


if __name__ == "__main__":
    run_gamepad_test()
