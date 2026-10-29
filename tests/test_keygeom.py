import json
import unittest
from pathlib import Path

from keygeom.record import TapCounter, build
from keygeom.spec import validate

ROOT = Path(__file__).parent.parent
EXAMPLES = ROOT / "examples"
LAYOUTS = ROOT / "layouts"


def doc(**blocks):
    return {"blocks": blocks}


def block(*names, **extra):
    return {"keys": {n: {"x": i, "y": 0} for i, n in enumerate(names)}, **extra}


class ValidateTest(unittest.TestCase):
    def test_examples_are_valid(self):
        for path in EXAMPLES.glob("*.json"):
            with self.subTest(path.name):
                self.assertEqual(validate(json.loads(path.read_text())), [])

    def test_layouts_are_valid_and_named_after_their_device(self):
        paths = sorted(LAYOUTS.glob("*.json"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(path.name):
                layout = json.loads(path.read_text())
                self.assertEqual(validate(layout), [])
                device = layout["device"]
                self.assertTrue(path.name.startswith(f"{device['vendor']}-{device['product']}-"))

    def test_minimal(self):
        self.assertEqual(validate(doc(a=block("KEY_A"))), [])

    def test_not_an_object(self):
        self.assertTrue(validate([]))

    def test_no_blocks(self):
        self.assertTrue(validate({"blocks": {}}))

    def test_bad_key_name(self):
        self.assertTrue(validate(doc(a=block("a"))))

    def test_key_in_two_blocks(self):
        self.assertTrue(validate(doc(a=block("KEY_A"), b=block("KEY_A"))))

    def test_overlap(self):
        d = doc(a={"keys": {"KEY_A": {"x": 0, "y": 0, "w": 2}, "KEY_B": {"x": 1, "y": 0}}})
        self.assertTrue(any("overlap" in e for e in validate(d)))

    def test_touching_keys_do_not_overlap(self):
        d = doc(a={"keys": {"KEY_A": {"x": 0, "y": 0, "w": 2}, "KEY_B": {"x": 2, "y": 0}}})
        self.assertEqual(validate(d), [])

    def test_negative_and_bad_sizes(self):
        self.assertTrue(validate(doc(a={"keys": {"KEY_A": {"x": -1, "y": 0}}})))
        self.assertTrue(validate(doc(a={"keys": {"KEY_A": {"x": 0, "y": 0, "w": 0}}})))

    def test_unknown_field(self):
        self.assertTrue(validate(doc(a={"keys": {"KEY_A": {"x": 0, "y": 0, "z": 1}}})))

    def test_placement(self):
        self.assertEqual(validate(doc(a=block("KEY_A"), b=block("KEY_B", left_of="a"))), [])

    def test_placement_unknown_block(self):
        self.assertTrue(validate(doc(a=block("KEY_A", right_of="nope"))))

    def test_two_placements(self):
        d = doc(a=block("KEY_A"), b=block("KEY_B"), c=block("KEY_C", left_of="a", below="b"))
        self.assertTrue(validate(d))

    def test_device_and_interface(self):
        d = doc(a=block("KEY_A", interface=0))
        d["device"] = {"bus": "usb", "vendor": "8089", "product": "0008"}
        self.assertEqual(validate(d), [])

    def test_bad_device(self):
        for device in ({"vendor": "8089"}, {"vendor": "8089", "product": "8"},
                       {"vendor": "8089", "product": "000A"}, {"vendor": 1, "product": "0008"},
                       {"vendor": "8089", "product": "0008", "serial": "x"}, "usb"):
            with self.subTest(device=device):
                self.assertTrue(validate({"device": device, **doc(a=block("KEY_A"))}))

    def test_bad_interface(self):
        for interface in (-1, "0", 1.5, True):
            with self.subTest(interface=interface):
                self.assertTrue(validate(doc(a=block("KEY_A", interface=interface))))

    def test_placement_cycle_reported_once(self):
        d = doc(a=block("KEY_A", left_of="b"), b=block("KEY_B", left_of="a"))
        self.assertEqual(len(validate(d)), 1)


class TapCounterTest(unittest.TestCase):
    def test_counts_taps(self):
        c = TapCounter(window=0.5)
        self.assertEqual(c.press("KEY_A", 0.0), [])
        self.assertEqual(c.press("KEY_A", 0.2), [])
        self.assertEqual(c.press("KEY_B", 0.4), [("KEY_A", 2)])
        self.assertEqual(c.poll(0.5), [])
        self.assertEqual(c.poll(1.0), [("KEY_B", 1)])

    def test_slow_repeat_is_a_new_tap(self):
        c = TapCounter(window=0.5)
        c.press("KEY_A", 0.0)
        self.assertEqual(c.press("KEY_A", 2.0), [("KEY_A", 1)])


class BuildTest(unittest.TestCase):
    def test_rows_go_bottom_to_top(self):
        d = build([("KEY_A", 1), ("KEY_B", 2), ("KEY_C", 1), ("KEY_D", 3)])
        self.assertEqual(d["blocks"]["main"]["keys"], {
            "KEY_A": {"x": 0, "y": 1}, "KEY_B": {"x": 1, "y": 1},
            "KEY_C": {"x": 0, "y": 0}, "KEY_D": {"x": 1, "y": 0}})
        self.assertEqual(validate(d), [])

    def test_blocks(self):
        d = build([("KEY_A", 3), ("KEY_B", 3)])
        self.assertEqual(list(d["blocks"]), ["block1", "block2"])

    def test_unfinished_row_and_block_are_kept(self):
        d = build([("KEY_A", 1), ("KEY_B", 1)])
        self.assertEqual(len(d["blocks"]["main"]["keys"]), 2)

    def test_finish_stops_recording(self):
        d = build([("KEY_A", 1), ("KEY_B", 4), ("KEY_C", 1)])
        self.assertEqual(list(d["blocks"]["main"]["keys"]), ["KEY_A", "KEY_B"])

    def test_late_tap_continues_the_last_key(self):
        d = build([("KEY_A", 1), ("KEY_B", 3), ("KEY_B", 1), ("KEY_C", 1)])
        self.assertEqual(list(d["blocks"]["main"]["keys"]), ["KEY_A", "KEY_B"])

    def test_duplicate_key(self):
        with self.assertRaises(ValueError):
            build([("KEY_A", 1), ("KEY_B", 1), ("KEY_A", 1)])

    def test_empty(self):
        with self.assertRaises(ValueError):
            build([])

    def test_device_and_interface_are_recorded(self):
        device = {"bus": "usb", "vendor": "8089", "product": "0008"}
        d = build([("KEY_A", 1)], device=device, interface=0)
        self.assertEqual(d["device"], device)
        self.assertEqual(d["blocks"]["main"]["interface"], 0)
        self.assertEqual(validate(d), [])

    def test_name(self):
        self.assertEqual(build([("KEY_A", 1)], name="pad")["name"], "pad")


if __name__ == "__main__":
    unittest.main()
