# Requirements

## Purpose and Scope

This catalog records the functional requirements (FR) and non-functional
requirements (NFR) observable in the current implementation of Yet Another
Way Out. It is a baseline specification, not a proposal for behavior beyond
the code. The evidence was reconciled across `README.md`,
`doc/software_architecture.md`, `python/way_out_game/`, and `python/tests/`.

The scope includes maze generation and state transitions, keyboard and
controller input, the pygame application loop, first-person and minimap
rendering, and the standalone gamepad visualizer. Packaging, installation,
and untested performance targets are outside this catalog.

## Traceability

Each requirement has a stable ID, one Gherkin Feature and Scenario, and
acceptance steps. `FR` identifies behavior; `NFR` identifies a measurable
quality or constraint. Behavioral requirements link to the Python test
functions that verify them. Engineering-quality requirements link to their
enforcing commands. Each Python test function carries the same requirement
ID and Gherkin header in its docstring, enabling reverse lookup from test to
requirement.

Requirements are marked **Implemented** because this document describes the
current baseline. A linked test is evidence for the stated behavior, not a
claim that every possible input has been exhaustively tested. Parameterized
pytest cases are listed by their shared test function.

## Functional Requirements

### FR-MAZ-001: Default playable maze

**Status:** Implemented

**Feature:** Procedural maze generation

**Scenario:** Generate the default playable maze

- **GIVEN** no custom dimensions are supplied
- **WHEN** a maze is generated
- **THEN** it is 23 by 17, has one interior wall-panel exit, and has a floor
  entry with an adjacent passage

**Tests:**

- `test_generated_maze_has_scaled_dimensions_and_one_exit`
  ([source](../python/tests/test_model.py#L36))

### FR-MAZ-002: Seeded generation

**Status:** Implemented

**Feature:** Reproducible maze generation

**Scenario:** A seed reproduces its maze

- **GIVEN** a maze generation seed
- **WHEN** mazes are generated with the same and different seeds
- **THEN** the same seed repeats its layout and other seeds can produce
  different layouts

**Tests:**

- `test_maze_generation_is_seeded_and_randomized`
  ([source](../python/tests/test_model.py#L67))

### FR-MAZ-003: Reachable exit

**Status:** Implemented

**Feature:** Connected maze passages

**Scenario:** The generated exit is reachable from the entry

- **GIVEN** a generated maze
- **WHEN** its passage and exit cells are traversed
- **THEN** the exit is reachable from the entry

**Tests:**

- `test_generated_exit_is_reachable_from_the_start`
  ([source](../python/tests/test_model.py#L82))

### FR-MAZ-004: Maze input validation

**Status:** Implemented

**Feature:** Maze construction and generation validation

**Scenario:** Invalid dimensions, grids, exits, or entries are rejected

- **GIVEN** even or undersized dimensions, malformed rows, invalid tiles,
  an invalid exit, or an entry that is not an in-bounds floor cell
- **WHEN** a maze is generated or constructed
- **THEN** a `ValueError` is raised

**Tests:**

- `test_maze_generator_rejects_even_or_too_small_dimensions`
  ([source](../python/tests/test_model.py#L108))
- `test_maze_rejects_invalid_layouts`
  ([source](../python/tests/test_model.py#L133))

### FR-STATE-001: Valid initial player position

**Status:** Implemented
**Feature:** Initial game state

**Scenario:** The initial player position must be floor

- **GIVEN** a requested starting position on a wall
- **WHEN** the initial state is created
- **THEN** a `ValueError` is raised

**Tests:**

- `test_initial_state_rejects_non_floor_position`
  ([source](../python/tests/test_model.py#L221))
**Status:** Implemented

**Feature:** Explored maze view
**Scenario:** The starting view reveals corridor cells up to the first wall

- **GIVEN** a player position, heading, and view depth
- **WHEN** initial exploration or visible cells are calculated
- **THEN** the player, forward corridor, and adjacent side panels are
  included, visibility stops at a blocking cell, and zero depth includes
  only the player

**Tests:**

- `test_initial_state_reveals_starting_corridor`
  ([source](../python/tests/test_model.py#L205))
  ([source](../python/tests/test_model.py#L250))
- `test_visible_cells_with_zero_depth_contains_only_player`
  ([source](../python/tests/test_model.py#L264))

### FR-ACT-001: Collision-safe animated actions

**Status:** Implemented

**Feature:** Player movement and turning

**Scenario:** A valid action animates and commits after eight frames

- **GIVEN** an idle, unsolved player and a movement or turn action
- **WHEN** the action is advanced through eight display frames
- **THEN** movement or facing commits, the animation clears, and blocked
  or out-of-bounds movement and overlapping actions leave state unchanged
- `test_direction_vectors`
  ([source](../python/tests/test_model.py#L187))
- `test_begin_action_starts_eight_frame_animation`
- `test_blocked_move_does_not_change_state`
  ([source](../python/tests/test_model.py#L296))
- `test_actions_are_ignored_while_animating`
  ([source](../python/tests/test_model.py#L310))
- `test_turn_commits_after_eight_frames`
  ([source](../python/tests/test_model.py#L325))
- `test_forward_commits_position_and_expands_map`
  ([source](../python/tests/test_model.py#L343))
- `test_backward_move_uses_opposite_direction`
  ([source](../python/tests/test_model.py#L360))
  ([source](../python/tests/test_model.py#L408))
- `test_animation_rejects_invalid_frame`
  ([source](../python/tests/test_model.py#L557))
  ([source](../python/tests/test_model.py#L584))

### FR-ACT-002: Animated camera pose

**Status:** Implemented

**Feature:** First-person movement animation

**Scenario:** Camera position and heading interpolate during an action

- **GIVEN** a movement or turn animation
- **WHEN** one animation frame advances
- **THEN** the camera pose moves a proportional amount toward the target

**Tests:**

- `test_view_pose_interpolates_movement`
  ([source](../python/tests/test_model.py#L523))
- `test_view_pose_interpolates_turn`
  ([source](../python/tests/test_model.py#L541))
**Status:** Implemented

**Feature:** Reaching the exit

**Scenario:** Reaching the exit panel solves the maze without entering it

- **GIVEN** the player is adjacent to the exit panel
- **WHEN** forward or backward movement completes at the exit
- **THEN** the game is solved, the player remains on floor, and the solution
  timer starts at zero

**Tests:**

- `test_backward_move_can_reach_exit`
  ([source](../python/tests/test_model.py#L375))
- `test_exit_solves_without_entering_wall`
  ([source](../python/tests/test_model.py#L421))

### FR-SOLVE-002: Victory countdown

**Status:** Implemented
**Scenario:** The visible countdown runs from ten to one over five seconds

- **GIVEN** a solved or unsolved game state
- **WHEN** the solution timer advances or its displayed value is queried
- **THEN** solved time is clamped at five seconds, the value decreases every
  half second, and no countdown is shown before a win or after completion

**Tests:**

- `test_solution_countdown_steps_every_half_second`
  ([source](../python/tests/test_model.py#L451))
- `test_solution_timer_advances_and_clamps`
  ([source](../python/tests/test_model.py#L466))
- `test_solution_timer_ignores_unsolved_state`
  ([source](../python/tests/test_model.py#L481))
  ([source](../python/tests/test_model.py#L511))

### FR-INP-001: Keyboard action mapping

**Status:** Implemented

**Feature:** Keyboard movement controls

**Scenario:** Cursor and WASD keys map to movement and turn actions

- **GIVEN** a supported cursor or WASD key
- **WHEN** the key is translated
- **THEN** the matching action is returned, while unsupported keys return
  no action

**Tests:**

- `test_keyboard_actions`
  ([source](../python/tests/test_input.py#L23))
- `test_unknown_key_has_no_action`
  ([source](../python/tests/test_input.py#L35))

### FR-INP-002: Analog and hat action mapping

**Status:** Implemented

**Feature:** Analog and hat input

**Scenario:** Deadzone and dominant-axis rules select an action

- **GIVEN** normalized horizontal and vertical axes
- **WHEN** the axes are translated
- **THEN** values at or inside the 0.55 deadzone return no action, the
  greater-magnitude axis selects direction, and vertical wins ties

**Tests:**

- `test_gamepad_axes`
  ([source](../python/tests/test_input.py#L57))
- `test_gamepad_deadzone`
  ([source](../python/tests/test_input.py#L70))
- `test_vertical_axis_wins_equal_magnitude_tie`
  ([source](../python/tests/test_input.py#L82))

### FR-APP-001: Polled gamepad movement and hot-plugging

**Status:** Implemented

**Feature:** Gamepad movement in the application

**Scenario:** Current stick state is polled for each connected controller

- **GIVEN** one or more attached controllers
- **WHEN** the application polls a frame or processes connection changes
- **THEN** current left-stick values can start actions, centered or stale
  input does not, each controller is independent, and added or removed
  devices do not leave stale repeating input

**Tests:**

- `test_run_game_opens_and_polls_left_stick`
  ([source](../python/tests/test_app.py#L68))
- `test_gamepad_hold_release_and_disconnect`
  ([source](../python/tests/test_app.py#L142))
- `test_gamepad_connected_after_startup`
  ([source](../python/tests/test_app.py#L187))
- `test_gamepad_can_connect_during_countdown`
  ([source](../python/tests/test_app.py#L405))
- `test_stale_axis_events_do_not_override_polled_input`
  ([source](../python/tests/test_app.py#L625))
- `test_held_joystick_starts_another_action`
  ([source](../python/tests/test_app.py#L690))
- `test_held_joystick_waits_until_animation_finishes`
  ([source](../python/tests/test_app.py#L705))
- `test_centered_joystick_does_not_start_action`
  ([source](../python/tests/test_app.py#L718))
- `test_idle_controller_does_not_block_another_gamepad`
  ([source](../python/tests/test_app.py#L731))

### FR-APP-002: Held-axis repeat timing

**Status:** Implemented

**Feature:** Continuous gamepad movement

**Scenario:** Held turns are throttled without delaying held walking

- **GIVEN** a controller holding a horizontal or vertical axis
- **WHEN** an action animation completes
- **THEN** turns repeat no more often than every 0.5 seconds per controller;
  release or direction change resets the turn deadline, while walking is
  not turn-throttled and busy or solved states do not consume a deadline

**Tests:**

- `test_held_turn_has_half_second_repeat_delay`
  ([source](../python/tests/test_app.py#L106))
- `test_turn_repeat_deadline`
  ([source](../python/tests/test_app.py#L755))
- `test_release_or_disconnect_during_animation_resets_turn_delay`
  ([source](../python/tests/test_app.py#L784))
- `test_opposite_turn_is_immediate`
  ([source](../python/tests/test_app.py#L808))
- `test_walking_repeats_without_turn_delay`
  ([source](../python/tests/test_app.py#L828))
- `test_turn_delay_is_per_controller`
  ([source](../python/tests/test_app.py#L856))
- `test_busy_game_does_not_consume_turn_repeat`
  ([source](../python/tests/test_app.py#L879))
- `test_solved_game_does_not_consume_turn_repeat`
  ([source](../python/tests/test_app.py#L896))

### FR-APP-003: Application event handling

**Status:** Implemented

**Feature:** Keyboard, hat, and window events

**Scenario:** Supported events act and quit while unrelated events are ignored

- **GIVEN** an active game and a pygame event
- **WHEN** the event is handled
- **THEN** supported key and hat events start actions, unrelated events leave
  state unchanged, and a window-close event stops the loop

**Tests:**

- `test_quit_remains_active_after_restart`
  ([source](../python/tests/test_app.py#L352))
- `test_key_event_starts_action`
  ([source](../python/tests/test_app.py#L453))
- `test_quit_event_stops_loop`
  ([source](../python/tests/test_app.py#L607))
- `test_joystick_hat_event_starts_turn`
  ([source](../python/tests/test_app.py#L657))
- `test_irrelevant_event_does_not_change_state`
  ([source](../python/tests/test_app.py#L674))
- `test_run_game_exits_on_quit_event`
  ([source](../python/tests/test_app.py#L930))

### FR-APP-004: Restart after victory

**Status:** Implemented

**Feature:** Starting a new maze after victory

**Scenario:** Restart input is accepted only after the countdown completes

- **GIVEN** a solved game before or after countdown completion
- **WHEN** a key, gamepad button, release, or motion event is handled
- **THEN** key or button-down restarts only after completion, other input is
  ignored, and restart creates a fresh maze and initial state

**Tests:**

- `test_game_loop_restart_after_countdown`
  ([source](../python/tests/test_app.py#L223))
- `test_any_key_restarts_a_solved_game`
  ([source](../python/tests/test_app.py#L470))
- `test_key_is_ignored_during_solution_countdown`
  ([source](../python/tests/test_app.py#L500))
- `test_gamepad_button_is_ignored_during_solution_countdown`
  ([source](../python/tests/test_app.py#L522))
- `test_gamepad_button_restarts_after_countdown`
  ([source](../python/tests/test_app.py#L544))
- `test_gamepad_release_or_motion_does_not_restart`
  ([source](../python/tests/test_app.py#L583))

### FR-APP-005: Preserve queued device events on restart

**Status:** Implemented

**Feature:** Restart event processing

**Scenario:** Restart does not discard queued connection changes

- **GIVEN** restart input and a gamepad connection event are queued together
- **WHEN** the completed game restarts
- **THEN** the connection event is still processed

**Tests:**

- `test_restart_preserves_queued_connection_changes`
  ([source](../python/tests/test_app.py#L286))

### FR-REN-001: Grid ray casting

**Status:** Implemented

**Feature:** First-person wall and exit detection

**Scenario:** A ray returns its first obstruction within the view range

- **GIVEN** an origin, angle, and maximum ray distance
- **WHEN** a ray is cast through the grid
- **THEN** the first wall or exit is identified with distance and side, or
  no hit is returned when nothing is reached within range

**Tests:**

- `test_ray_hits_wall_at_known_distance`
  ([source](../python/tests/test_rendering.py#L39))
- `test_ray_hits_exit_panel`
  ([source](../python/tests/test_rendering.py#L55))
- `test_ray_returns_none_past_short_range`
  ([source](../python/tests/test_rendering.py#L70))
- `test_ray_handles_zero_components`
  ([source](../python/tests/test_rendering.py#L82))

### FR-REN-002: Ego-centered exploration map

**Status:** Implemented

**Feature:** Minimap rendering

**Scenario:** The map centers the player and orients forward at the top

- **GIVEN** a player state and explored maze cells
- **WHEN** the minimap is drawn
- **THEN** the player remains centered, forward remains up, and explored
  cells outside current visibility remain distinguishable

**Tests:**

- `test_minimap_draws_to_surface`
  ([source](../python/tests/test_rendering.py#L110))
- `test_minimap_draws_explored_floor_outside_current_view`
  ([source](../python/tests/test_rendering.py#L124))
- `test_minimap_centers_player_and_keeps_forward_up`
  ([source](../python/tests/test_rendering.py#L142))

### FR-REN-003: First-person and victory presentation

**Status:** Implemented

**Feature:** Scene rendering and animated exit

**Scenario:** The scene draws walls, the animated exit, and victory state

- **GIVEN** a maze, player state, and elapsed game time
- **WHEN** the scene is drawn
- **THEN** the first-person view renders, exit plasma varies across position
  and time, solved state shows a countdown, and completion shows a restart
  prompt

**Tests:**

- `test_plasma_color_varies_across_both_axes_and_time`
  ([source](../python/tests/test_rendering.py#L95))
- `test_scene_draws_and_animates_exit`
  ([source](../python/tests/test_rendering.py#L166))
- `test_scene_handles_rays_with_no_hit_in_view_range`
  ([source](../python/tests/test_rendering.py#L181))
- `test_scene_draws_solved_overlay`
  ([source](../python/tests/test_rendering.py#L207))
- `test_scene_offers_restart_after_countdown`
  ([source](../python/tests/test_rendering.py#L232))

### FR-PAD-001: Optional gamepad backend

**Status:** Implemented

**Feature:** Keyboard-only operation

**Scenario:** The gamepad backend supports zero attached devices

- **GIVEN** no connected gamepads
- **WHEN** connected devices are opened and polled
- **THEN** the backend returns no sticks and opens no device

**Tests:**

- `test_no_devices`
  ([source](../python/tests/test_gamepad.py#L24))

### FR-PAD-002: Gamepad lifecycle by instance ID

**Status:** Implemented

**Feature:** Shared gamepad backend

**Scenario:** Added and removed devices update backend state exactly once

- **GIVEN** an attached device and a duplicate added notification
- **WHEN** the device is removed by instance ID
- **THEN** device, resting-axis, and stick state are cleared and hardware is
  released

**Tests:**

- `test_device_lifecycle`
  ([source](../python/tests/test_gamepad.py#L42))

### FR-PAD-003: Variable gamepad capabilities

**Status:** Implemented

**Feature:** Gamepad axis polling

**Scenario:** Missing axes are treated as centered

- **GIVEN** a gamepad exposing fewer axes than the left stick requires
- **WHEN** the backend polls its stick
- **THEN** absent axes read as zero and repeated close is harmless

**Tests:**

- `test_device_with_fewer_axes`
  ([source](../python/tests/test_gamepad.py#L79))

### FR-PAD-004: Independent controllers

**Status:** Implemented

**Feature:** Multiple gamepad support

**Scenario:** Removing one controller preserves another controller's state

- **GIVEN** two controllers with independent instance IDs and axis values
- **WHEN** one controller is removed
- **THEN** the other controller retains its values and remains available

**Tests:**

- `test_multiple_controllers_keep_independent_values`
  ([source](../python/tests/test_gamepad.py#L107))

### FR-VIZ-001: Raw gamepad snapshots

**Status:** Implemented

**Feature:** Gamepad state inspection

**Scenario:** A snapshot reads every raw control safely

- **GIVEN** a device with axes, buttons, and hats
- **WHEN** a gamepad snapshot is read
- **THEN** all present controls are captured and absent indices use safe
  defaults

**Tests:**

- `test_snapshot_reads_every_control`
  ([source](../python/tests/test_gamepad_script.py#L50))

### FR-VIZ-002: Gamepad control visualization

**Status:** Implemented

**Feature:** Visualizer control feedback

**Scenario:** Pressed controls highlight in both mapped and raw views

- **GIVEN** a supported gamepad button, stick, trigger, hat, or extra control
- **WHEN** its state changes between idle and active
- **THEN** the matching rendered control highlights and returns to idle;
  empty control sets render safely

**Tests:**

- `test_controls_highlight_and_release`
  ([source](../python/tests/test_gamepad_script.py#L81))
- `test_remapped_silhouette_buttons`
  ([source](../python/tests/test_gamepad_script.py#L124))
- `test_upper_middle_button_is_wide_rectangle`
  ([source](../python/tests/test_gamepad_script.py#L169))
- `test_dpad_button_highlights_both_views`
  ([source](../python/tests/test_gamepad_script.py#L191))
- `test_empty_device_renders`
  ([source](../python/tests/test_gamepad_script.py#L233))

### FR-VIZ-003: Visualizer device lifecycle

**Status:** Implemented

**Feature:** Gamepad visualizer lifecycle

**Scenario:** The visualizer supports absent, connected, and changing devices

- **GIVEN** zero or more gamepads that may connect or disconnect at runtime
- **WHEN** the visualizer runs, switches selection, or receives an exit event
- **THEN** it remains usable, tracks devices by identity, and closes on quit
  or Escape

**Tests:**

- `test_no_gamepad_loop`
  ([source](../python/tests/test_gamepad_script.py#L252))
- `test_exit_events`
  ([source](../python/tests/test_gamepad_script.py#L272))
- `test_hotplug_switch_and_disconnect`
  ([source](../python/tests/test_gamepad_script.py#L291))
- `test_startup_device_and_duplicate_event`
  ([source](../python/tests/test_gamepad_script.py#L348))

### FR-VIZ-004: Dynamic visualizer sizing

**Status:** Implemented

**Feature:** Gamepad visualizer layout

**Scenario:** The window expands to fit devices with many controls

- **GIVEN** a gamepad with more axes, buttons, or hats than the base layout
- **WHEN** its controls are drawn
- **THEN** the visualizer expands the window to contain the extra readouts

**Tests:**

- `test_large_device_expands_window`
  ([source](../python/tests/test_gamepad_script.py#L375))

## Non-Functional Requirements

### NFR-DESIGN-001: Immutable domain values

**Status:** Implemented

**Feature:** Immutable game domain

**Scenario:** Maze and game state values cannot be mutated in place

- **GIVEN** a constructed maze or game state
- **WHEN** a field is assigned
- **THEN** the frozen value rejects the mutation

**Tests:**

- `test_maze_is_immutable`
  ([source](../python/tests/test_model.py#L165))
- `test_game_state_is_immutable`
  ([source](../python/tests/test_model.py#L570))

### NFR-APP-001: Application resource cleanup

**Status:** Implemented

**Feature:** Application resource lifecycle

**Scenario:** Exceptional exits release pygame and controller resources

- **GIVEN** an open controller and a rendering or controller-read failure
- **WHEN** the application exits exceptionally
- **THEN** the error propagates and pygame and opened devices are closed

**Tests:**

- `test_game_closes_gamepad_on_render_error`
  ([source](../python/tests/test_app.py#L387))
- `test_game_closes_gamepad_on_read_error`
  ([source](../python/tests/test_app.py#L435))

### NFR-TEST-001: Headless bounded game loop

**Status:** Implemented

**Feature:** Automated application testability

**Scenario:** The game loop can run without physical display or audio hardware

- **GIVEN** SDL dummy video and audio drivers
- **WHEN** the application runs for a bounded number of frames
- **THEN** the loop completes without physical hardware

**Tests:**

- `test_run_game_can_execute_headlessly`
  ([source](../python/tests/test_app.py#L913))

### NFR-VIZ-001: Visualizer resource cleanup

**Status:** Implemented

**Feature:** Visualizer resource lifecycle

**Scenario:** A rendering failure releases open devices and pygame

- **GIVEN** an open gamepad and a renderer that raises an error
- **WHEN** the visualizer exits exceptionally
- **THEN** the error propagates and the device and pygame are closed

**Tests:**

- `test_cleanup_after_render_error`
  ([source](../python/tests/test_gamepad_script.py#L416))

### NFR-QUAL-001: Linter and static analysis checks

**Status:** Implemented

**Feature:** Source and documentation quality

**Scenario:** Code and documentation pass the configured analyzers

- **GIVEN** Python source or project documentation changes
- **WHEN** the configured static analysis and lint commands are run
- **THEN** Ruff, Flake8, Pylint, Mypy, and Markdownlint exit successfully

**Verification:** Run Python checks from `python/`; run Markdownlint from the
repository root.

```powershell
uv run ruff check .
uv run flake8 way_out.py way_out_game script tests check_coverage.py
uv run pylint way_out.py way_out_game script tests check_coverage.py
uv run mypy --explicit-package-bases --config-file ..\mypy.ini `
  way_out.py way_out_game script tests check_coverage.py
npx --yes markdownlint-cli2 --config .markdownlint.json README.md `
  doc/software_architecture.md doc/requirements.md
```

### NFR-QUAL-002: Python formatting check

**Status:** Implemented

**Feature:** Consistent Python formatting

**Scenario:** Python source conforms to the configured Black format

- **GIVEN** Python source changes
- **WHEN** the Black check is run
- **THEN** Black reports no files requiring formatting

**Verification:** Run from `python/`.

```powershell
uv run black --check .
```

### NFR-COV-001: Strict per-metric coverage floor

**Status:** Implemented

**Feature:** Automated test coverage

**Scenario:** Each coverage metric is greater than 95 percent

- **GIVEN** the complete pytest suite and its branch coverage data
- **WHEN** pytest and the coverage checker are run
- **THEN** statement coverage is greater than 95 percent
- **AND** line coverage is greater than 95 percent
- **AND** function coverage is greater than 95 percent
- **AND** branch coverage is greater than 95 percent
- **AND** both commands succeed

**Verification:** Run both commands from `python/`.

```powershell
uv run pytest
uv run python check_coverage.py
```

## Quality Notes

Pytest also enforces a 95% combined coverage threshold. The stricter
per-metric requirement above is enforced by `check_coverage.py`, which fails
at or below 95% for any metric. Function coverage counts named functions
with executable statements; module-level code is excluded. Run the full suite
before the checker because isolated test files may not meet the combined
coverage gates.
