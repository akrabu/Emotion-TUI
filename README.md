# Emotion-TUI

A small terminal emotion logger. Choose an energy/pleasantness quadrant, pick
an emotion or enter your own, and optionally add a note. Entries are saved
locally in a CSV file.

## Run

Requires Python 3.11 or newer with `curses`, on Linux or macOS. There are no
third-party Python dependencies. Use a terminal with at least 22 rows and
80 columns; wider terminals show more of the emotion grid.

```sh
cp config.example.toml config.toml
python3 log_emotion.py
```

The included configuration contains a generic starter vocabulary. Edit
`config.toml` to change the emotion words, quadrant titles, or colors.

## Controls

- Arrow keys or `h/j/k/l`: move between quadrants and emotions.
- Enter: choose a quadrant or emotion, or save a note.
- `Custom...`: type an emotion that is not in the list.
- `b`: return from the emotion grid to the quadrant selector.
- Escape in a note: return to the grid without logging the selection.
- Enter on an empty note: log the emotion without a note.
- `q` or Escape in the picker: quit without logging.

The grid scrolls as you move. Each quadrant uses six columns, with emotions
laid out from left to right. Colors are terminal palette names: `red`,
`yellow`, `blue`, `green`, `cyan`, `magenta`, and `white`.

## Configuration and data

Configuration is searched in this order:

1. `config.toml` in the current working directory.
2. `config.toml` beside the script.
3. `~/.config/emotion-tui/config.toml`.

`log_file` accepts an absolute path or a path relative to the configuration
file. The example writes `emotion_log.csv` beside `config.toml`. If omitted,
the log defaults to that same directory; for a config in
`~/.config/emotion-tui`, it defaults to
`${XDG_DATA_HOME:-~/.local/share}/emotion-tui/emotion_log.csv`.

CSV columns are `Date & Time`, `Quadrant`, `Emotion`, and `Notes`. Timestamps
use the computer's local time. Logs are plain text and are not encrypted.
User configuration and generated CSV files are ignored by Git.

```sh
python3 log_emotion.py --no-log
python3 log_emotion.py --env
```

`--no-log` prints the selected emotion without writing a record. `--env`
prints shell-quoted exports for `EMOTION` and `EMOTION_QUADRANT`; combine it
with `--no-log` to avoid logging. The picker uses `/dev/tty` when stdout is
redirected, allowing `emotion="$(python3 log_emotion.py --no-log)"`.

## Tests

```sh
python3 -m unittest -v
```

Tests use temporary files and invented entries.

## License

MIT. See [LICENSE](LICENSE).
