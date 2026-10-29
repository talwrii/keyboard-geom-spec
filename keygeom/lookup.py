"""Find a layout by device, and the key at a coordinate in it."""
import json
import re
from pathlib import Path

from .spec import validate

# The layouts/ folder of a checkout (which is also where an editable install finds it).
DEFAULT_LAYOUTS = Path(__file__).resolve().parent.parent / "layouts"

ID_RE = re.compile(r"^[0-9a-fA-F]{4}:[0-9a-fA-F]{4}$")


def _load(path):
    with open(path) as f:
        doc = json.load(f)
    errors = validate(doc)
    if errors:
        raise ValueError(f"{path} is not a valid layout: {errors[0]}")
    return doc


def find_layout(spec, layouts_dir=DEFAULT_LAYOUTS):
    """Return (path, layout) for `spec`: a layout file, a `VENDOR:PRODUCT` id, or part of a name.

    Names are matched case-insensitively against each layout's `name` and file name.
    Raises ValueError if nothing matches, or if several layouts do.
    """
    if Path(spec).is_file():
        return Path(spec), _load(spec)

    layouts_dir = Path(layouts_dir)
    if not layouts_dir.is_dir():
        raise ValueError(f"no layouts folder at {layouts_dir} (and {spec!r} is not a file)")

    if ID_RE.match(spec):
        vendor, product = spec.lower().split(":")

        def matches(path, doc):
            device = doc.get("device", {})
            return device.get("vendor") == vendor and device.get("product") == product
    else:
        needle = spec.casefold()

        def matches(path, doc):
            return needle in f"{doc.get('name', '')} {path.stem}".casefold()

    found = []
    for path in sorted(layouts_dir.glob("*.json")):
        try:
            doc = _load(path)
        except (OSError, ValueError):
            continue  # a broken layout should not hide the others
        if matches(path, doc):
            found.append((path, doc))

    if not found:
        raise ValueError(f"no layout matches {spec!r} in {layouts_dir}")
    if len(found) > 1:
        names = ", ".join(path.name for path, _ in found)
        raise ValueError(f"{spec!r} matches several layouts: {names}")
    return found[0]


def key_at(layout, x, y, block=None):
    """The name of the key covering (x, y) in `block` of `layout`, or None if there is none.

    A key covers x0 <= x < x0 + w and y0 <= y < y0 + h, so a wide or tall key answers
    for every unit it spans. `block` may be left out if the layout has only one.
    """
    blocks = layout["blocks"]
    if block is None:
        if len(blocks) != 1:
            raise ValueError("the layout has several blocks, choose one: " + ", ".join(blocks))
        block = next(iter(blocks))
    elif block not in blocks:
        raise ValueError(f"no block {block!r}; the blocks are: " + ", ".join(blocks))
    for name, key in blocks[block]["keys"].items():
        if (key["x"] <= x < key["x"] + key.get("w", 1)
                and key["y"] <= y < key["y"] + key.get("h", 1)):
            return name
    return None
