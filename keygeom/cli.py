import argparse
import json
import sys

from .spec import validate


def main(argv=None):
    parser = argparse.ArgumentParser(prog="keygeom", description="Describe a keyboard's physical key layout.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="check keygeom files against the spec")
    p.add_argument("files", nargs="+", metavar="FILE")

    p = sub.add_parser("record", help="create a keygeom file by pressing the keys of a device in order")
    p.add_argument("device", help="evdev device, e.g. /dev/input/event21")
    p.add_argument("-o", "--output", help="file to write (default: stdout)")
    p.add_argument("--name", help="human readable name for the layout")
    p.add_argument("--window", type=float, default=0.45, help="seconds within which taps of one key count together")
    p.add_argument("--no-grab", action="store_true", help="let other programs see the keys as well")

    args = parser.parse_args(argv)

    if args.command == "validate":
        bad = False
        for path in args.files:
            try:
                with open(path) as f:
                    errors = validate(json.load(f))
            except (OSError, ValueError) as e:
                errors = [str(e)]
            for e in errors:
                print(f"{path}: {e}", file=sys.stderr)
            bad = bad or bool(errors)
        return 1 if bad else 0

    from .record import record
    try:
        doc = record(args.device, name=args.name, window=args.window, grab=not args.no_grab)
    except (OSError, ValueError) as e:
        print(f"keygeom: {e}", file=sys.stderr)
        return 1
    text = json.dumps(doc, indent=2) + "\n"
    if args.output:
        with open(args.output, "w") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    return 0
