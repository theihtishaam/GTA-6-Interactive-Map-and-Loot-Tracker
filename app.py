"""Start GTA 6 Loot Map. Use --stop to close it."""
import sys
from os.path import abspath, dirname


def main():
    if sys.version_info < (3, 10):
        print("GTA 6 Loot Map needs Python 3.10 or newer. On Windows, double-click Start Atlas.cmd for automatic setup.")
        return 1

    # Windows embeddable Python isolates sys.path from the script's directory.
    project = dirname(abspath(__file__))
    if project not in sys.path:
        sys.path.insert(0, project)
    from launch_atlas import main as launch
    return launch()


if __name__ == "__main__":
    sys.exit(main())
