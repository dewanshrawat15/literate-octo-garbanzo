"""Management CLI for the Spell Bee backend.

Usage
-----
    python manage.py --set-admin <username>

Promotes the given user to admin. The server does not need to be running.
"""
import argparse
import sys

from db.database import init_all_tables
from db.repositories import UserRepository


def _set_admin(username: str) -> None:
    init_all_tables()
    repo = UserRepository()
    if not repo.find_by_username(username):
        print(f"Error: user '{username}' not found.", file=sys.stderr)
        sys.exit(1)
    success = repo.set_admin(username)
    if success:
        print(f"Success: '{username}' is now an admin.")
    else:
        print(f"Error: failed to update '{username}'.", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Spell Bee management commands")
    parser.add_argument(
        "--set-admin",
        metavar="USERNAME",
        help="Promote the given user to admin",
    )
    args = parser.parse_args()

    if args.set_admin:
        _set_admin(args.set_admin)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
