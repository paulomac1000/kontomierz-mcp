"""python -m kontomierz_mcp entry point."""

import sys

from .server import main

if __name__ == "__main__":
    sys.exit(main())
