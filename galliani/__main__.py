"""Spec 018 R23: `python -m galliani` runs the terminal entry point, the same as `galliacli`.

The entry point is imported here, not in `galliani/__init__.py`, so `import galliani` stays light.
"""

import sys


def _main() -> int:
    from galliani.tui.entry import main

    return main()


if __name__ == "__main__":
    sys.exit(_main())
