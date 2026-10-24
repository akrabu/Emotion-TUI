# Copyright (C) 2026 akrabu
# SPDX-License-Identifier: MIT
# See LICENSE for the full license text.

import contextlib
import csv
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import log_emotion as app


class EmotionLogTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.path = self.directory / "entries.csv"
        self.quadrant = {"title": "Low Energy\nPleasant"}
        self.config = {"log_file": str(self.path), "auto_log": True}

    def test_csv_preserves_notes_and_has_one_header(self):
        note = 'An invented note, with "quotes" and\na second line.'
        app.log_emotion(self.config, self.quadrant, "Calm", note)
        app.log_emotion(self.config, self.quadrant, "Content", "")
        with self.path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.reader(stream))
        self.assertEqual(rows[0], ["Date & Time", "Quadrant", "Emotion", "Notes"])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1][1:], ["Low Energy / Pleasant", "Calm", note])
        self.assertEqual(rows[2][2:], ["Content", ""])

    def test_legacy_csv_keeps_existing_entries_when_notes_are_added(self):
        with self.path.open("w", newline="", encoding="utf-8") as stream:
            csv.writer(stream).writerows([
                ["Date & Time", "Quadrant", "Emotion"],
                ["2000-01-01 12:00:00", "Low Energy / Pleasant", "Calm"],
            ])
        app.log_emotion(self.config, self.quadrant, "Content", "Example")
        with self.path.open(newline="", encoding="utf-8") as stream:
            rows = list(csv.reader(stream))
        self.assertEqual(rows[1], ["2000-01-01 12:00:00", "Low Energy / Pleasant", "Calm", ""])
        self.assertEqual(len(rows), 3)

    def test_relative_log_path_is_always_relative_to_config(self):
        config_path = self.directory / "config.toml"
        self.assertEqual(
            app.resolve_log_file("data/entries.csv", config_path),
            self.directory / "data" / "entries.csv",
        )

    def test_user_config_defaults_to_data_directory(self):
        config_path = self.directory / "config.toml"
        data = self.directory / "data"
        with patch.object(app, "USER_CONFIG_PATH", config_path), patch.dict(os.environ, {"XDG_DATA_HOME": str(data)}):
            self.assertEqual(
                app.default_log_file(config_path.resolve()),
                data / "emotion-tui" / "emotion_log.csv",
            )

    def test_sample_configuration_loads_without_creating_a_log(self):
        sample = Path(app.__file__).with_name("config.example.toml")
        target = self.directory / "config.toml"
        target.write_text(sample.read_text(encoding="utf-8"), encoding="utf-8")
        with patch.object(app, "CONFIG_PATHS", (target,)):
            config = app.load_config()
        self.assertEqual(len(config["quadrants"]), 4)
        self.assertEqual(config["log_file"], str(self.directory / "emotion_log.csv"))
        self.assertFalse(Path(config["log_file"]).exists())
        for quadrant in config["quadrants"]:
            self.assertEqual(len(quadrant["emotions"]), 12)

    def test_no_log_option_only_prints_the_selection(self):
        with patch("sys.argv", ["log_emotion.py", "--no-log"]), patch.object(app, "load_config", return_value=self.config), patch.object(app, "curses_on_tty", return_value=(self.quadrant, "Calm", "Example")), contextlib.redirect_stdout(io.StringIO()) as output:
            app.main()
        self.assertEqual(output.getvalue(), "Calm\n")
        self.assertFalse(self.path.exists())

    def test_cancel_does_not_create_a_log(self):
        with patch("sys.argv", ["log_emotion.py"]), patch.object(app, "load_config", return_value=self.config), patch.object(app, "curses_on_tty", return_value=None):
            with self.assertRaises(SystemExit) as raised:
                app.main()
        self.assertEqual(raised.exception.code, 1)
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
