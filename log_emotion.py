#!/usr/bin/env python3
# Copyright (C) 2026 akrabu
# SPDX-License-Identifier: MIT
# See LICENSE for the full license text.

import argparse
import csv
import curses
import os
import shlex
import sys
import tomllib
import textwrap
from datetime import datetime
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
USER_CONFIG_PATH = Path("~/.config/emotion-tui/config.toml").expanduser()
CONFIG_PATHS = (
    Path.cwd() / "config.toml",
    SCRIPT_DIR / "config.toml",
    USER_CONFIG_PATH,
)

DICTIONARY_EMOTION_INPUT_LEN = len("hippopotomonstrosesquippedaliophobia")


COLOR_NAMES = {
    "red": curses.COLOR_RED,
    "yellow": curses.COLOR_YELLOW,
    "blue": curses.COLOR_BLUE,
    "green": curses.COLOR_GREEN,
    "cyan": curses.COLOR_CYAN,
    "magenta": curses.COLOR_MAGENTA,
    "white": curses.COLOR_WHITE,
}


def unique_paths(paths):
    seen = set()
    unique = []

    for path in paths:
        resolved = path.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)

    return unique


def default_log_file(config_path):
    if config_path == USER_CONFIG_PATH.resolve():
        data_home = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser()
        return data_home / "emotion-tui" / "emotion_log.csv"
    return config_path.parent / "emotion_log.csv"


def resolve_log_file(value, config_path):
    path = Path(value).expanduser()
    if path.is_absolute():
        return path

    return config_path.parent / path


def load_config():
    config_paths = unique_paths(CONFIG_PATHS)
    config_path = next((path for path in config_paths if path.exists()), None)

    if config_path is None:
        paths = ", ".join(str(path) for path in config_paths)
        print(f"Missing config file. Checked: {paths}", file=sys.stderr)
        sys.exit(1)

    with config_path.open("rb") as f:
        config = tomllib.load(f)

    if "quadrants" not in config:
        print("Config needs at least one [[quadrants]] section.", file=sys.stderr)
        sys.exit(1)

    if "log_file" in config:
        config["log_file"] = str(resolve_log_file(config["log_file"], config_path))
    else:
        config["log_file"] = str(default_log_file(config_path))

    config.setdefault("auto_log", True)

    return config


def safe_addstr(win, y, x, text, attr=0):
    h, w = win.getmaxyx()
    if y < 0 or y >= h or x < 0 or x >= w:
        return

    max_len = max(0, w - x - 1)
    if max_len <= 0:
        return

    try:
        win.addnstr(y, x, text, max_len, attr)
    except curses.error:
        pass


def center_text(win, y, text, attr=0):
    _, w = win.getmaxyx()
    x = max(0, (w - len(text)) // 2)
    safe_addstr(win, y, x, text, attr)


QUADRANT_COLS = 6
VISIBLE_EMOTION_COLS = QUADRANT_COLS


def setup_colors(config):
    curses.start_color()
    curses.use_default_colors()

    for idx, quadrant in enumerate(config["quadrants"], start=1):
        color_name = quadrant.get("color", "white").lower()
        bg = COLOR_NAMES.get(color_name, curses.COLOR_WHITE)

        if color_name in ("green", "yellow"):
            fg = curses.COLOR_BLACK
        else:
            fg = curses.COLOR_WHITE

        curses.init_pair(idx, fg, bg)


def draw_filled_box(win, y, x, height, width, lines, color_pair, selected=False):
    attr = curses.color_pair(color_pair)
    if selected:
        attr |= curses.A_BOLD

    for row in range(height):
        safe_addstr(win, y + row, x, " " * width, attr)

    if selected:
        safe_addstr(win, y, x, ">" + (" " * max(0, width - 2)) + "<", attr | curses.A_BOLD)

    start_y = y + max(1, (height - len(lines)) // 2)

    for i, line in enumerate(lines):
        line = line[: max(1, width - 2)]
        text_x = x + max(1, (width - len(line)) // 2)
        safe_addstr(win, start_y + i, text_x, line, attr) # | curses.A_BOLD)


def draw_quadrants(stdscr, config, selected):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    quadrants = config["quadrants"]

    center_text(stdscr, 0, "How do you feel right now?", curses.A_BOLD)
    center_text(stdscr, 1, "Choose a quadrant, then press Enter")

    # Compact layout for short screens like the MicroJournal
    card_h = 4
    gap_y = 1
    top = 3

    card_w = max(18, (w - 6) // 2)
    left_x = 2
    right_x = 4 + card_w

    positions = [
        (top, left_x),
        (top, right_x),
        (top + card_h + gap_y, left_x),
        (top + card_h + gap_y, right_x),
    ]

    for i, quadrant in enumerate(quadrants[:4]):
        y, x = positions[i]

        # Do not skip bottom quadrants unless truly impossible
        if y >= h - 2:
            continue

        draw_filled_box(
            stdscr,
            y,
            x,
            min(card_h, h - y - 2),
            min(card_w, w - x - 1),
            quadrant["title"].splitlines(),
            i + 1,
            selected == i,
        )

    safe_addstr(stdscr, h - 1, 1, "Arrows/hjkl: move  Enter: choose  q: quit")
    stdscr.refresh()


def emotions_for_quadrant(config, quadrant_index):
    return config["quadrants"][quadrant_index]["emotions"] + ["Custom..."]


def quadrant_grid_bounds(config):
    row_counts = [
        max(1, (len(emotions_for_quadrant(config, idx)) + QUADRANT_COLS - 1) // QUADRANT_COLS)
        for idx in range(min(4, len(config["quadrants"])))
    ]

    while len(row_counts) < 4:
        row_counts.append(1)

    low_energy_top = max(row_counts[0], row_counts[1]) + 1

    return [
        {"row": 0, "col": 0, "rows": row_counts[0]},
        {"row": 0, "col": QUADRANT_COLS, "rows": row_counts[1]},
        {"row": low_energy_top, "col": 0, "rows": row_counts[2]},
        {"row": low_energy_top, "col": QUADRANT_COLS, "rows": row_counts[3]},
    ]


def emotion_position(config, quadrant_index, emotion_index):
    bounds = quadrant_grid_bounds(config)[quadrant_index]
    return (
        bounds["row"] + emotion_index // QUADRANT_COLS,
        bounds["col"] + emotion_index % QUADRANT_COLS,
    )


def emotion_cells(config):
    cells = []

    quadrant_count = min(4, len(config["quadrants"]))

    for quadrant_index, _bounds in enumerate(quadrant_grid_bounds(config)[:quadrant_count]):
        for emotion_index, label in enumerate(emotions_for_quadrant(config, quadrant_index)):
            row, col = emotion_position(config, quadrant_index, emotion_index)
            cells.append(
                {
                    "quadrant": quadrant_index,
                    "emotion": emotion_index,
                    "label": label,
                    "row": row,
                    "col": col,
                }
            )

    return cells


def visible_grid_rows(height, top):
    return max(1, (height - top - 1) // 2)


def emotion_scroll(config, quadrant_index, emotion_index, height):
    top = 3
    rows = visible_grid_rows(height, top)
    bounds = quadrant_grid_bounds(config)[quadrant_index]
    selected_row, _ = emotion_position(config, quadrant_index, emotion_index)

    scroll_row = bounds["row"]
    if selected_row >= scroll_row + rows:
        scroll_row = selected_row - rows + 1
    elif selected_row < scroll_row:
        scroll_row = selected_row

    return scroll_row, bounds["col"], rows


def move_emotion_selection(config, quadrant_index, emotion_index, direction):
    selected_row, selected_col = emotion_position(config, quadrant_index, emotion_index)
    candidates = []

    for cell in emotion_cells(config):
        row = cell["row"]
        col = cell["col"]

        if direction == "left" and col < selected_col:
            score = (abs(row - selected_row), selected_col - col)
        elif direction == "right" and col > selected_col:
            score = (abs(row - selected_row), col - selected_col)
        elif direction == "up" and row < selected_row:
            score = (abs(col - selected_col), selected_row - row)
        elif direction == "down" and row > selected_row:
            score = (abs(col - selected_col), row - selected_row)
        else:
            continue

        candidates.append((score, cell["quadrant"], cell["emotion"]))

    if not candidates:
        return quadrant_index, emotion_index

    _, next_quadrant, next_emotion = min(candidates)
    return next_quadrant, next_emotion


def draw_emotions(stdscr, config, quadrant_index, selected):
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    title = config["quadrants"][quadrant_index]["title"].replace("\n", " / ")
    center_text(stdscr, 0, title, curses.A_BOLD)
    center_text(stdscr, 1, "Choose the closest specific emotion")

    cell_w = max(1, (w - 2) // VISIBLE_EMOTION_COLS)
    cell_h = 2
    top = 3
    scroll_row, scroll_col, visible_rows = emotion_scroll(config, quadrant_index, selected, h)
    selected_count = len(emotions_for_quadrant(config, quadrant_index))

    for cell in emotion_cells(config):
        if not (scroll_row <= cell["row"] < scroll_row + visible_rows):
            continue
        if not (scroll_col <= cell["col"] < scroll_col + VISIBLE_EMOTION_COLS):
            continue

        row = cell["row"] - scroll_row
        col = cell["col"] - scroll_col
        y = top + row * cell_h
        x = 1 + col * cell_w

        attr = curses.color_pair(cell["quadrant"] + 1)

        if cell["quadrant"] == quadrant_index and cell["emotion"] == selected:
            attr |= curses.A_BOLD | curses.A_REVERSE

        label_width = max(1, cell_w - 2)
        label = cell["label"][:label_width]
        chip = f" {label.center(label_width)} "
        safe_addstr(stdscr, y, x, chip[:cell_w], attr)

    safe_addstr(stdscr, h - 2, 2, "Arrows/hjkl: move   Enter: choose   b: back   q: quit")
    safe_addstr(stdscr, h - 2, max(2, w - 12), f"{selected + 1}/{selected_count}")
    stdscr.refresh()


def longest_emotion_length(config):
    return max(
        (len(emotion) for quadrant in config["quadrants"] for emotion in quadrant["emotions"]),
        default=0,
    )


def prompt_custom_emotion(stdscr, min_input_len=0):
    h, w = stdscr.getmaxyx()
    prompt = "Custom emotion: "
    desired_input_len = max(12, DICTIONARY_EMOTION_INPUT_LEN, min_input_len)
    popup_h = min(5, h)
    popup_w = min(max(32, len(prompt) + desired_input_len + 4), w)
    popup_y = max(0, (h - popup_h) // 2)
    popup_x = max(0, (w - popup_w) // 2)
    input_y = min(2, popup_h - 1)
    input_x = min(2 + len(prompt), popup_w - 1)
    max_len = max(1, popup_w - input_x - 2)
    popup = curses.newwin(popup_h, popup_w, popup_y, popup_x)
    popup.keypad(True)
    value = []

    try:
        curses.curs_set(1)
    except curses.error:
        pass

    while True:
        popup.erase()
        popup.box()
        center_text(popup, 0, " Custom ")
        safe_addstr(popup, input_y, 2, prompt, curses.A_BOLD)
        safe_addstr(popup, input_y, input_x, "".join(value))
        popup.move(input_y, min(popup_w - 2, input_x + len(value)))
        popup.refresh()

        key = popup.get_wch()

        if key in ("\n", "\r", curses.KEY_ENTER):
            break
        if key in ("\x1b",):
            value = []
            break
        if key in (curses.KEY_BACKSPACE, "\b", "\x7f"):
            if value:
                value.pop()
            continue
        if isinstance(key, str) and key.isprintable() and len(value) < max_len:
            value.append(key)

    try:
        curses.curs_set(0)
    except curses.error:
        pass

    return "".join(value).strip()


def prompt_emotion_note(stdscr, quadrant_index, emotion):
    h, w = stdscr.getmaxyx()
    prefix = "Explore why you might be feeling "
    suffix = ":"
    instruction = "Enter: save   Esc: back"
    popup_h = min(7, h)
    popup_w = min(max(82, len(prefix) + len(emotion) + len(suffix) + 42), w)
    popup_y = max(0, (h - popup_h) // 2)
    popup_x = max(0, (w - popup_w) // 2)
    content_w = max(1, popup_w - 4)
    prompt_y = 1
    input_y = max(1, min(popup_h - 3, 3))
    input_x = 2
    max_visible = max(1, popup_w - input_x - 2)
    max_len = 500
    popup = curses.newwin(popup_h, popup_w, popup_y, popup_x)
    popup.keypad(True)
    value = []

    try:
        curses.curs_set(1)
    except curses.error:
        pass

    while True:
        popup.erase()
        popup.box()

        full_prompt = f"{prefix}{emotion}{suffix}"
        if len(full_prompt) <= content_w:
            safe_addstr(popup, prompt_y, 2, prefix, curses.A_BOLD)
            safe_addstr(
                popup,
                prompt_y,
                2 + len(prefix),
                emotion,
                curses.color_pair(quadrant_index + 1) | curses.A_BOLD,
            )
            safe_addstr(popup, prompt_y, 2 + len(prefix) + len(emotion), suffix, curses.A_BOLD)
        else:
            emotion_label = f"{emotion}{suffix}"
            if content_w >= 3:
                emotion_label = textwrap.shorten(emotion_label, width=content_w, placeholder="...")
            else:
                emotion_label = emotion_label[:content_w]

            safe_addstr(popup, prompt_y, 2, prefix.strip(), curses.A_BOLD)
            safe_addstr(
                popup,
                prompt_y + 1,
                2,
                emotion_label,
                curses.color_pair(quadrant_index + 1) | curses.A_BOLD,
            )

        note = "".join(value)
        visible_note = note[-max_visible:]
        safe_addstr(popup, input_y, input_x, visible_note)
        safe_addstr(popup, popup_h - 2, 2, instruction)
        popup.move(input_y, min(popup_w - 2, input_x + len(visible_note)))
        popup.refresh()

        key = popup.get_wch()

        if key in ("\n", "\r", curses.KEY_ENTER):
            break
        if key in ("\x1b",):
            return None
        if key in (curses.KEY_BACKSPACE, "\b", "\x7f"):
            if value:
                value.pop()
            continue
        if isinstance(key, str) and key.isprintable() and len(value) < max_len:
            value.append(key)

    try:
        curses.curs_set(0)
    except curses.error:
        pass

    return "".join(value).strip()


def run_ui(stdscr, config):
    curses.curs_set(0)
    stdscr.keypad(True)
    setup_colors(config)

    screen = "quadrants"
    quadrant_index = 0
    emotion_index = 0

    while True:
        if screen == "quadrants":
            draw_quadrants(stdscr, config, quadrant_index)
        else:
            draw_emotions(stdscr, config, quadrant_index, emotion_index)

        key = stdscr.getch()

        if key in (ord("q"), 27):
            return None

        if screen == "quadrants":
            if key in (curses.KEY_LEFT, ord("h")) and quadrant_index % 2 == 1:
                quadrant_index -= 1
            elif key in (curses.KEY_RIGHT, ord("l")) and quadrant_index % 2 == 0:
                quadrant_index += 1
            elif key in (curses.KEY_UP, ord("k")) and quadrant_index >= 2:
                quadrant_index -= 2
            elif key in (curses.KEY_DOWN, ord("j")) and quadrant_index <= 1:
                quadrant_index += 2
            elif key in (10, 13, curses.KEY_ENTER):
                screen = "emotions"
                emotion_index = 0

        elif screen == "emotions":
            emotions = emotions_for_quadrant(config, quadrant_index)

            if key == ord("b"):
                screen = "quadrants"
            elif key in (curses.KEY_LEFT, ord("h")):
                quadrant_index, emotion_index = move_emotion_selection(
                    config, quadrant_index, emotion_index, "left"
                )
            elif key in (curses.KEY_RIGHT, ord("l")):
                quadrant_index, emotion_index = move_emotion_selection(
                    config, quadrant_index, emotion_index, "right"
                )
            elif key in (curses.KEY_UP, ord("k")):
                quadrant_index, emotion_index = move_emotion_selection(
                    config, quadrant_index, emotion_index, "up"
                )
            elif key in (curses.KEY_DOWN, ord("j")):
                quadrant_index, emotion_index = move_emotion_selection(
                    config, quadrant_index, emotion_index, "down"
                )
            elif key in (10, 13, curses.KEY_ENTER):
                quadrant = config["quadrants"][quadrant_index]
                emotion = emotions[emotion_index]

                if emotion == "Custom...":
                    emotion = prompt_custom_emotion(stdscr, longest_emotion_length(config))
                    if not emotion:
                        continue

                notes = prompt_emotion_note(stdscr, quadrant_index, emotion)
                if notes is None:
                    continue

                return quadrant, emotion, notes


def curses_on_tty(config):
    """
    This lets command substitution work:

        EMOTION="$(python3 log_emotion.py --no-log)"

    The TUI uses /dev/tty, while the final selected value still prints to stdout.
    """
    if sys.stdin.isatty() and sys.stdout.isatty():
        return curses.wrapper(lambda stdscr: run_ui(stdscr, config))

    with open("/dev/tty", "r+b", buffering=0) as tty:
        old_stdin = os.dup(0)
        old_stdout = os.dup(1)

        try:
            os.dup2(tty.fileno(), 0)
            os.dup2(tty.fileno(), 1)
            return curses.wrapper(lambda stdscr: run_ui(stdscr, config))
        finally:
            os.dup2(old_stdin, 0)
            os.dup2(old_stdout, 1)
            os.close(old_stdin)
            os.close(old_stdout)


def update_existing_log_header(path):
    if not path.exists() or path.stat().st_size == 0:
        return

    with path.open("r", newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))

    if not rows or rows[0] != ["Date & Time", "Quadrant", "Emotion"]:
        return

    rows[0].append("Notes")
    for row in rows[1:]:
        if len(row) == 3:
            row.append("")

    with path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


def log_emotion(config, quadrant, emotion, notes):
    path = Path(config["log_file"]).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    update_existing_log_header(path)

    now = datetime.now()
    quadrant_title = quadrant["title"].replace("\n", " / ")
    needs_header = not path.exists() or path.stat().st_size == 0

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if needs_header:
            writer.writerow(["Date & Time", "Quadrant", "Emotion", "Notes"])
        writer.writerow([now.strftime("%Y-%m-%d %H:%M:%S"), quadrant_title, emotion, notes])


def print_env(quadrant, emotion):
    quadrant_text = quadrant["title"].replace("\n", " / ")
    print(f"export EMOTION={shlex.quote(emotion)}")
    print(f"export EMOTION_QUADRANT={shlex.quote(quadrant_text)}")


def main():
    parser = argparse.ArgumentParser(description="Choose an emotion and optionally save a note to CSV.")
    parser.add_argument("--env", action="store_true", help="Print shell exports for EMOTION variables.")
    parser.add_argument("--no-log", action="store_true", help="Do not append to the emotion log.")
    args = parser.parse_args()

    config = load_config()
    result = curses_on_tty(config)

    if result is None:
        sys.exit(1)

    quadrant, emotion, notes = result

    if config.get("auto_log", True) and not args.no_log:
        log_emotion(config, quadrant, emotion, notes)

    if args.env:
        print_env(quadrant, emotion)
    else:
        print(emotion)


if __name__ == "__main__":
    main()
