import argparse

from dotenv import load_dotenv


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Big Learning Gym")
    parser.add_argument("--workspace", help="Local workspace JSON file")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    legacy = commands.add_parser("import-legacy")
    legacy.add_argument("path")
    serve = commands.add_parser("serve")
    serve.add_argument("--port", type=int)
    commands.add_parser("worker")
    commands.add_parser("backup").add_argument("path")
    commands.add_parser("restore").add_argument("path")
    frontend = commands.add_parser("frontend").add_subparsers(dest="frontend_command", required=True)
    frontend.add_parser("check").add_argument("directory")
    frontend.add_parser("install").add_argument("directory")
    frontend.add_parser("export-kit").add_argument("directory")
    args = parser.parse_args()
    import os

    from .workspaces import load_workspace

    if args.workspace:
        os.environ["GYM_WORKSPACE"] = args.workspace
    workspace = load_workspace()
    if args.command == "frontend":
        from .frontend_kit import export_kit, install_frontend
        from .frontends import check_frontend

        if args.frontend_command == "export-kit":
            print(export_kit(args.directory))
        elif args.frontend_command == "install":
            print(install_frontend(args.directory, os.getenv("GYM_WORKSPACE")))
        else:
            print(check_frontend(args.directory))
        return
    if args.command == "serve":
        import uvicorn

        uvicorn.run("gym.api:create_app", factory=True, host="127.0.0.1", port=args.port or workspace.port)
    elif args.command == "worker":
        import sys

        from .worker import main as worker

        sys.argv = [sys.argv[0]]
        worker()
    else:
        store = workspace.store()
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
