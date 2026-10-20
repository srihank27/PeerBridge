"""Explicit seed/reset/evaluate commands for the local prototype."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.peerbridge import db


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('seed', 'reset', 'evaluate'))
    parser.add_argument('--confirm', action='store_true', help='Confirm replacement of local demo data for reset.')
    args = parser.parse_args()
    if args.command == 'reset':
        if not args.confirm:
            parser.error('reset replaces local demo changes; pass --confirm to continue')
        db.init_database()
        db.reset_database()
        print('Reset the fictional SQLite demo. No real student data is included.')
    elif args.command == 'seed':
        db.init_database()
        print('Demo initialized; existing local changes were preserved.')
    else:
        from backend.peerbridge.evaluation import evaluate
        print(json.dumps(evaluate(), indent=2))


if __name__ == '__main__':
    main()
