"""Backward-compat entry point: `python main.py ...` still works.

Canonical usage is `python -m jarvis.main ...` or the `jarvis` console script.
"""

from jarvis.main import main

if __name__ == "__main__":
    main()
