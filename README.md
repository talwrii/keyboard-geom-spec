# keygeom
A standard for describing the physical layout of a keyboard-like device such as a keyboard or a numpad. Scripts are Linux only.

Tools to record this layout and validate layout. A database of the standard for these devices. If you want to use such a layout and avoid collision on Linux you might like to use [linux-event-triggers](https://github.com/talwrii/linux-event-triggers) (the `evtrig` command)

This code is AI-generated and unreviewed.

## Motivation
I bought some numpads and macroboards and did not know what the physical keys did (necessary for mapping them). I wanted to record the layout for the device and share it on the internet, but found no standards.

## Alternatives and prior work
**[QMK](https://github.com/qmk/qmk_firmware)'s `info.json`** ([reference](https://docs.qmk.fm/reference_info_json)) is the closest match. Each key has a `matrix: [row, col]` (its wiring position) and an `x`/`y`/`w`/`h` (its position and size in key units). But `info.json` only exists for keyboards that run QMK firmware, and it maps geometry to a matrix position, not to a keycode; that needs a separate, per-user keymap. A generic numpad was never going to have one. It also describes one flat list of keys at absolute positions, with no named blocks or placement of blocks relative to each other.

**XKB's geometry files** (`/usr/share/X11/xkb/geometry/*.xkb`) are an older version of the same idea: a handful of standard physical keyboard shapes (`pc104`, `pc105` and some vendor shapes), used so that X11 tools can draw a picture of a normal keyboard. Only standard layouts are supported; they can't describe arbitrary hardware.

## The format
A keygeom file is JSON. A layout is made of named **blocks** of keys: the main section of a keyboard, a numpad, the F-key row, one half of a split keyboard. Each key is a Linux evdev key and has a position.

```json
{
  "name": "Standard numpad",
  "blocks": {
    "numpad": {
      "keys": {
        "KEY_KP7": {"x": 0, "y": 0},
        "KEY_KP8": {"x": 1, "y": 0},
        "KEY_KP9": {"x": 2, "y": 0},
        "KEY_KP0": {"x": 0, "y": 1, "w": 2}
      }
    }
  }
}
```

See [`examples/standard-numpad.json`](examples/standard-numpad.json) for a full one.

### Top level
| field    | required | |
|----------|----------|-|
| `blocks` | yes      | object mapping block names to blocks. At least one. |
| `name`   | no       | human readable name of the layout. |
| `device` | no       | which kind of hardware this describes. See below. |

### Device
Identifies the *model* of hardware the layout is for, so a tool can pick the right layout for a device it finds.

You can find a device's ids with `lsusb`: in a line like `Bus 001 Device 016: ID 8089:0008 SayoDevice SayoDevice 6x4F`, the `8089:0008` is `vendor:product`.

| field     | required | |
|-----------|----------|-|
| `vendor`  | yes      | USB or Bluetooth vendor id: 4 lowercase hex digits, as `lsusb` prints it, e.g. `"8089"`. |
| `product` | yes      | product id, in the same form, e.g. `"0008"`. |
| `bus`     | no       | `"usb"` or `"bluetooth"` (or another bus name). |

Nothing that identifies one particular unit or socket belongs here: not serial numbers, not `/dev/input/eventN` numbers and not USB port paths. Event numbers are handed out in the order devices appear, so they change when a device is replugged or the machine reboots.

### Blocks
| field                                    | required | |
|------------------------------------------|----------|-|
| `keys`                                   | yes      | object mapping key names to keys. At least one. |
| `interface`                              | no       | USB interface number the block's keys arrive on. One physical device often appears as several evdev nodes, one per USB interface, and only one of them may carry the keys. |
| `left_of`, `right_of`, `above`, `below`  | no       | name of another block. This block sits on that side of the named block. At most one per block. |

Each block has its own coordinate space with its origin at the top left of the block. Placement is relative and approximate: it says which side a block is on, not how far away it is. A block with no placement has no stated position relative to the others. Placement must not form a cycle.

### Keys
A key's name is its Linux evdev key name (from `linux/input-event-codes.h`), such as `KEY_A`, `KEY_KP7` or `BTN_LEFT`. This is the key the device sends, not what is printed on the keycap. A key name may appear only once in a file.

| field | required | default | |
|-------|----------|---------|-|
| `x`   | yes      |         | left edge, in key units, `>= 0` |
| `y`   | yes      |         | top edge, in key units, `>= 0`; `y` increases downwards |
| `w`   | no       | 1       | width in key units, `> 0` |
| `h`   | no       | 1       | height in key units, `> 0` |

One key unit is the pitch of a standard keycap (19.05 mm). Keys in a block may not overlap. Any other field is an error.

## Layouts
The [`layouts/`](layouts/) folder holds layouts for real devices as they come, with their default keymap, one file each, named `<vendor>-<product>-<slug>.json` after the device's USB ids, e.g. [`8089-0008-sayodevice-6x4f.json`](layouts/8089-0008-sayodevice-6x4f.json). Every layout has a `device`, and its file name must start with that device's `vendor` and `product`. The tests check every file there.

### Submitting a layout
I would like layouts for more devices. To submit one:

1. **Record it.** Run `keygeom record` on the device (see [Recording](#recording)), which fills in the `device` ids for you.
2. **Edit it if you need to.** Add wide or tall keys, gaps and block placement by hand, and give it a `name` such as the product name.
3. **Validate it.** `keygeom validate yourfile.json` must print nothing.
4. **Name it** `<vendor>-<product>-<slug>.json`, for example `1a2c-9d01-semico-usb-gaming-keyboard.json`: lowercase, with hyphens.
5. **Send it** as a pull request that adds the file to `layouts/`.

Please check:
- **One model per file.** A layout describes a model, not your unit. The `device` has no serial number, and nothing in the file should be specific to your machine.
- **The keys are what the device sends.** Keys are named by the evdev code the device sends, not by the legend printed on the keycap. A layout is taken to be for the device's default keymap, so if you recorded a device you had reprogrammed, say so in the `name`, e.g. "SayoDevice 6x4F (custom keymap)".
- **No duplicates.** If the device already has a file, say what differs, for example a different firmware or key configuration.

By submitting a layout you agree that it is released under this project's [MIT licence](LICENSE).

## Installation
```
pipx install keygeom
```
Or from a checkout: `pipx install -e .`

## Validating
```
keygeom validate layout.json [more.json ...]
```
Prints each problem as `file: message` and exits with status 1 if there were any. From Python:

```python
from keygeom import validate
errors = validate(json.load(open("layout.json")))   # [] if valid
```

## Looking up a key
```
keygeom key 8089:0008 4 1
KEY_4
```
Prints the key at a column and row of a device's layout, **counted from 1** at the top left: `4 1` is the fourth column of the first row. A wide or tall key answers for every column or row it covers. If there is no key there, nothing is printed and the exit status is 1.

(Positions in the layout file are different: they are in key units counted from 0, and may be fractions. `keygeom key` takes whole column and row numbers and does the conversion.)

The device is a `VENDOR:PRODUCT` id (run `lsusb` and look for the `ID` on your device's line, e.g. `ID 8089:0008`), part of a layout's name (`keygeom key sayodevice 1 6`) or a layout file. Ids and names are looked up in [`layouts/`](layouts/), or in the folder given with `--layouts`. If the layout has more than one block, choose one with `--block`.

This lets a script refer to a key by where it is rather than by what it sends, for example to bind the top-right key of a pad with [linux-event-triggers](https://github.com/talwrii/linux-event-triggers): `evtrig --serial $SERIAL --bind "$(keygeom key 8089:0008 4 1)=tmux next-window"`.

From Python, `find_layout` and `key_at` are in `keygeom`. They use the file's positions, counted from 0, not the 1-based numbers of the command.

## Recording
```
keygeom record /dev/input/event21 --name "My pad" -o layout.json
```
Press the keys in physical order, **bottom-left to top-right**. Tap the last key of a row **twice** to end the row. Tap the last key of a block **three times** to end the block. Tap the very last key **four times** to end the recording. (Ctrl+C also stops it; a row or block you did not finish is closed for you.)

Taps of one key count together if they are within 0.45 seconds of each other (`--window` changes this). Each tap is echoed to stderr as you go.

The recorder fills in `device` (vendor, product and bus) and each block's `interface` from the device it is reading. The `interface` is only filled in for USB devices.

The recorder makes one block per triple tap, named `block1`, `block2`... (or `main` if there is only one), and places keys at whole-unit positions in the order you pressed them. It cannot know about wide or tall keys, gaps, or where blocks sit relative to each other: edit the file for those, then run `keygeom validate` on it.

The device must be readable by you, and not already grabbed by another program: a key remapper such as `keyd` will have to be told to leave the device alone. While recording, keys from the device are not delivered to other programs (`--no-grab` disables this).

Find the device with `evtest`, or `grep -A5 'Name=' /proc/bus/input/devices`.

## Tests
```
python3 -m unittest discover -s tests -t .
```
