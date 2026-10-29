import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from keygeom.cli import main
from keygeom.lookup import DEFAULT_LAYOUTS, find_layout, key_at

EXAMPLES = Path(__file__).parent.parent / "examples"

NUMPAD = {
    "name": "Test numpad",
    "device": {"vendor": "1234", "product": "abcd"},
    "blocks": {"main": {"keys": {
        "KEY_KP7": {"x": 0, "y": 0}, "KEY_KP8": {"x": 1, "y": 0},
        "KEY_KP0": {"x": 0, "y": 1, "w": 2}, "KEY_KPENTER": {"x": 2, "y": 0, "h": 2},
    }}},
}


class KeyAtTest(unittest.TestCase):
    def test_finds_keys(self):
        self.assertEqual(key_at(NUMPAD, 0, 0), "KEY_KP7")
        self.assertEqual(key_at(NUMPAD, 1, 0), "KEY_KP8")

    def test_wide_and_tall_keys_cover_every_unit(self):
        self.assertEqual(key_at(NUMPAD, 0, 1), "KEY_KP0")
        self.assertEqual(key_at(NUMPAD, 1, 1), "KEY_KP0")
        self.assertEqual(key_at(NUMPAD, 2, 0), "KEY_KPENTER")
        self.assertEqual(key_at(NUMPAD, 2, 1), "KEY_KPENTER")

    def test_points_inside_a_key(self):
        self.assertEqual(key_at(NUMPAD, 0.5, 0.9), "KEY_KP7")
        self.assertEqual(key_at(NUMPAD, 1.99, 1.5), "KEY_KP0")

    def test_empty_space_and_outside(self):
        self.assertIsNone(key_at(NUMPAD, 3, 0))
        self.assertIsNone(key_at(NUMPAD, 0, 2))
        self.assertIsNone(key_at(NUMPAD, -1, 0))

    def test_several_blocks_need_a_choice(self):
        layout = {"blocks": {"a": {"keys": {"KEY_A": {"x": 0, "y": 0}}},
                             "b": {"keys": {"KEY_B": {"x": 0, "y": 0}}}}}
        with self.assertRaises(ValueError):
            key_at(layout, 0, 0)
        self.assertEqual(key_at(layout, 0, 0, "b"), "KEY_B")
        with self.assertRaises(ValueError):
            key_at(layout, 0, 0, "c")


class FindLayoutTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        (self.dir / "1234-abcd-test-numpad.json").write_text(json.dumps(NUMPAD))

    def test_by_id(self):
        path, layout = find_layout("1234:abcd", self.dir)
        self.assertEqual(path.name, "1234-abcd-test-numpad.json")
        self.assertEqual(layout["name"], "Test numpad")

    def test_id_is_case_insensitive(self):
        self.assertEqual(find_layout("1234:ABCD", self.dir)[0].name, "1234-abcd-test-numpad.json")

    def test_by_name(self):
        self.assertEqual(find_layout("test NUMPAD", self.dir)[0].name, "1234-abcd-test-numpad.json")

    def test_by_file(self):
        path = self.dir / "1234-abcd-test-numpad.json"
        self.assertEqual(find_layout(str(path), self.dir / "nothing-here")[0], path)

    def test_no_match(self):
        with self.assertRaises(ValueError):
            find_layout("9999:0000", self.dir)

    def test_ambiguous(self):
        (self.dir / "1234-abcd-other-firmware.json").write_text(json.dumps(NUMPAD))
        with self.assertRaises(ValueError) as cm:
            find_layout("1234:abcd", self.dir)
        self.assertIn("several", str(cm.exception))

    def test_broken_layouts_do_not_hide_others(self):
        (self.dir / "0000-0000-broken.json").write_text("{not json")
        self.assertEqual(find_layout("1234:abcd", self.dir)[0].name, "1234-abcd-test-numpad.json")

    def test_missing_folder(self):
        with self.assertRaises(ValueError):
            find_layout("1234:abcd", self.dir / "nothing-here")


class CommandTest(unittest.TestCase):
    """`keygeom key` counts columns and rows from 1."""

    def run_key(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                status = main(["key", *argv])
            except SystemExit as e:
                status = e.code
        return status, out.getvalue().strip(), err.getvalue()

    def test_counts_from_one(self):
        self.assertEqual(self.run_key("8089:0008", "4", "1")[:2], (0, "KEY_4"))   # top right
        self.assertEqual(self.run_key("8089:0008", "1", "6")[:2], (0, "KEY_N"))   # bottom left

    def test_wide_key_answers_for_each_column(self):
        for column in ("1", "2"):
            self.assertEqual(self.run_key(str(EXAMPLES / "standard-numpad.json"), column, "5")[1], "KEY_KP0")

    def test_zero_is_rejected(self):
        self.assertNotEqual(self.run_key("8089:0008", "0", "1")[0], 0)

    def test_no_key(self):
        status, out, err = self.run_key("8089:0008", "9", "9")
        self.assertEqual((status, out), (1, ""))
        self.assertIn("column 9, row 9", err)


class RealLayoutsTest(unittest.TestCase):
    def test_sayodevice_top_right_key(self):
        _, layout = find_layout("8089:0008", DEFAULT_LAYOUTS)
        self.assertEqual(key_at(layout, 3, 0), "KEY_4")      # top right
        self.assertEqual(key_at(layout, 0, 5), "KEY_N")      # bottom left


if __name__ == "__main__":
    unittest.main()
