import argparse

from dotenv import load_dotenv


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Big Learning Gym")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    legacy = commands.add_parser("import-legacy")
    legacy.add_argument("path")
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int, default=8787)
    commands.add_parser("worker")
    commands.add_parser("backup").add_argument("path")
    commands.add_parser("restore").add_argument("path")
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run("gym.api:create_app", factory=True, host="127.0.0.1", port=args.port)
    elif args.command == "worker":
        import sys

        from .worker import main as worker

        sys.argv = [sys.argv[0]]
        worker()
    else:
        from .store import Store

        store = Store()
        if args.command == "import-legacy":
            from .importer import import_legacy

            print(import_legacy(store, args.path))
        elif args.command in {"backup", "restore"}:
            from . import backup

            print(getattr(backup, args.command)(store, args.path))
        else:
            print("Database initialized")


if __name__ == "__main__":
    main()
