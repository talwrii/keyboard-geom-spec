"""Validation for keygeom documents."""
import re

PLACEMENTS = ("left_of", "right_of", "above", "below")
KEY_RE = re.compile(r"^(KEY|BTN)_[A-Z0-9_]+$")
HEX_ID_RE = re.compile(r"^[0-9a-f]{4}$")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _fields(obj, allowed, where, errors):
    unknown = set(obj) - set(allowed)
    if unknown:
        errors.append(f"{where}: unknown fields: " + ", ".join(sorted(unknown)))


def validate(doc):
    """Return a list of problems with `doc`; empty if it is a valid keygeom document."""
    if not isinstance(doc, dict):
        return ["document must be an object"]
    errors = []
    _fields(doc, ("name", "device", "blocks"), "document", errors)
    if "device" in doc:
        errors += _device(doc["device"])
    blocks = doc.get("blocks")
    if not isinstance(blocks, dict) or not blocks:
        return errors + ["'blocks' must be a non-empty object"]

    owner = {}
    for bname, block in blocks.items():
        where = f"block {bname!r}"
        if not isinstance(block, dict):
            errors.append(f"{where}: must be an object")
            continue
        _fields(block, ("keys", "interface", *PLACEMENTS), where, errors)
        if "interface" in block and (not isinstance(block["interface"], int)
                                     or isinstance(block["interface"], bool) or block["interface"] < 0):
            errors.append(f"{where}: 'interface' must be an integer >= 0")
        keys = block.get("keys")
        if not isinstance(keys, dict) or not keys:
            errors.append(f"{where}: 'keys' must be a non-empty object")
            continue

        for kname, k in keys.items():
            kw = f"{where} key {kname!r}"
            if not KEY_RE.match(kname):
                errors.append(f"{kw}: not an evdev key name (KEY_* or BTN_*)")
            if kname in owner:
                errors.append(f"{kw}: also in block {owner[kname]!r}")
            owner.setdefault(kname, bname)
            if not isinstance(k, dict):
                errors.append(f"{kw}: must be an object")
                continue
            _fields(k, ("x", "y", "w", "h"), kw, errors)
            for f in ("x", "y"):
                if not _num(k.get(f)) or k[f] < 0:
                    errors.append(f"{kw}: '{f}' must be a number >= 0")
            for f in ("w", "h"):
                if f in k and (not _num(k[f]) or k[f] <= 0):
                    errors.append(f"{kw}: '{f}' must be a number > 0")

        given = [p for p in PLACEMENTS if p in block]
        if len(given) > 1:
            errors.append(f"{where}: at most one of {', '.join(PLACEMENTS)}")
        for p in given:
            if block[p] not in blocks or block[p] == bname:
                errors.append(f"{where}: {p} must name a different block")

    return errors or _geometry(blocks)


def _device(device):
    if not isinstance(device, dict):
        return ["device: must be an object"]
    errors = []
    _fields(device, ("bus", "vendor", "product"), "device", errors)
    for f in ("vendor", "product"):
        if not isinstance(device.get(f), str) or not HEX_ID_RE.match(device[f]):
            errors.append(f"device: '{f}' must be 4 lowercase hex digits, e.g. \"8089\"")
    if "bus" in device and not isinstance(device["bus"], str):
        errors.append("device: 'bus' must be a string such as \"usb\"")
    return errors


def _geometry(blocks):
    """Checks that need the structure to be sound: overlapping keys, placement cycles."""
    errors = []
    for bname, block in blocks.items():
        rects = [(n, k["x"], k["y"], k["x"] + k.get("w", 1), k["y"] + k.get("h", 1))
                 for n, k in block["keys"].items()]
        for i, (n1, ax0, ay0, ax1, ay1) in enumerate(rects):
            for n2, bx0, by0, bx1, by1 in rects[i + 1:]:
                if ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1:
                    errors.append(f"block {bname!r}: keys {n1!r} and {n2!r} overlap")

    for start in blocks:
        seen, b = [], start
        while b is not None and b not in seen:
            seen.append(b)
            b = next((blocks[b][p] for p in PLACEMENTS if p in blocks[b]), None)
        if b == start and start == min(seen):
            errors.append("block placement forms a cycle: " + " -> ".join(seen + [start]))
    return errors
