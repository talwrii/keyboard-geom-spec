"""Build a keygeom document by pressing the keys of a device in physical order.

Press the keys bottom row to top row, left to right within a row. Tap the last key of
a row twice to end the row, the last key of a block three times to end the block, and
the last key of the layout four times to finish recording.
"""
import re
import select
import sys
import time

END_ROW = 2
END_BLOCK = 3
FINISH = 4


class TapCounter:
    """Collapse repeated presses of one key within `window` seconds into (key, count)."""

    def __init__(self, window=0.45):
        self.window = window
        self.key = None
        self.count = 0
        self.last = 0.0

    @property
    def pending(self):
        return self.key is not None

    def press(self, key, t):
        """Register a press; return the taps this finishes (zero or one of them)."""
        if self.key == key and t - self.last <= self.window:
            self.count += 1
            done = []
        else:
            done = self.flush()
            self.key, self.count = key, 1
        self.last = t
        return done

    def poll(self, t):
        """Return the pending tap once no further press can extend it."""
        if self.pending and t - self.last > self.window:
            return self.flush()
        return []

    def flush(self):
        if not self.pending:
            return []
        tap = (self.key, self.count)
        self.key, self.count = None, 0
        return [tap]


def merge_taps(taps):
    """Join consecutive taps of one key: each key is recorded once, so a repeat continues the last."""
    merged = []
    for key, count in taps:
        if merged and merged[-1][0] == key:
            merged[-1] = (key, merged[-1][1] + count)
        else:
            merged.append((key, count))
    return merged


def build(taps, name=None, device=None, interface=None):
    """Build a keygeom document from a list of (key, count) taps.

    `device` ({"bus", "vendor", "product"}) and the USB `interface` the keys came from
    are recorded in the document when known.
    """
    blocks, rows, row, seen = [], [], [], set()
    for key, count in merge_taps(taps):
        if key in seen:
            raise ValueError(f"{key} was recorded twice")
        seen.add(key)
        row.append(key)
        if count >= END_ROW:
            rows.append(row)
            row = []
        if count >= END_BLOCK:
            blocks.append(rows)
            rows = []
        if count >= FINISH:
            break
    if row:
        rows.append(row)
    if rows:
        blocks.append(rows)
    if not blocks:
        raise ValueError("no keys were recorded")

    names = ["main"] if len(blocks) == 1 else [f"block{i + 1}" for i in range(len(blocks))]
    out = {}
    for block_name, block_rows in zip(names, blocks):
        keys = {}
        for i, block_row in enumerate(block_rows):  # pressed bottom to top, y counts down
            for x, key in enumerate(block_row):
                keys[key] = {"x": x, "y": len(block_rows) - 1 - i}
        out[block_name] = {"interface": interface, "keys": keys} if interface is not None else {"keys": keys}
    doc = {"blocks": out}
    if device:
        doc = {"device": device, **doc}
    return {"name": name, **doc} if name else doc


BUSES = {0x03: "usb", 0x05: "bluetooth"}


def device_identity(dev):
    """Return (device, interface) describing an evdev InputDevice; either may be None."""
    info = dev.info
    device = {"vendor": f"{info.vendor:04x}", "product": f"{info.product:04x}"}
    if info.bustype in BUSES:
        device = {"bus": BUSES[info.bustype], **device}
    match = re.search(r"/input(\d+)$", dev.phys or "")
    interface = int(match.group(1)) if match and info.bustype == 0x03 else None
    return device, interface


def _key_name(code):
    from evdev import ecodes
    name = ecodes.bytype[ecodes.EV_KEY].get(code)
    if isinstance(name, list):
        name = name[0]
    return name or f"KEY_{code}"


def record(path, name=None, window=0.45, grab=True):
    """Read presses from the evdev device at `path` until a FINISH tap or Ctrl+C; return a document."""
    import evdev
    from evdev import ecodes

    dev = evdev.InputDevice(path)
    if grab:
        dev.grab()
    counter, taps = TapCounter(window), []
    finished = False

    def note(done):
        nonlocal finished
        for key, count in done:
            taps.append((key, count))
            finished = merge_taps(taps)[-1][1] >= FINISH
            what = {1: "", END_ROW: "  <- end of row", END_BLOCK: "  <- end of block"}
            print(f"{key} x{count}{what.get(count, '  <- finish')}", file=sys.stderr)

    print(f"recording from {dev.name}; tap the last key {FINISH} times when done", file=sys.stderr)
    try:
        while not finished:
            ready, _, _ = select.select([dev.fd], [], [], window if counter.pending else None)
            if ready:
                for ev in dev.read():
                    if ev.type == ecodes.EV_KEY and ev.value == 1:
                        note(counter.press(_key_name(ev.code), time.monotonic()))
            note(counter.poll(time.monotonic()))
    except KeyboardInterrupt:
        note(counter.flush())
    finally:
        if grab:
            dev.ungrab()
    return build(taps, name, *device_identity(dev))
