"""Local launch configuration, not a tenant or learner domain model."""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

NAME = re.compile(r"^[a-z][a-z0-9-]{0,63}$")
ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Workspace:
    id: str = "default"
    port: int = 8787
    data_dir: Path | None = None
    database_url: str | None = None
    frontends: tuple[Path, ...] = field(default_factory=tuple)

    def store(self):
        from .store import Store

        return Store(self.database_url, self.data_dir)


def load_workspace(path=None):
    """Explicit paths resolve relative to the configuration, never the shell cwd."""
    path = path or os.getenv("GYM_WORKSPACE")
    if not path:
        return Workspace()
    source = Path(path).expanduser().resolve()
    data = json.loads(source.read_text())
    unknown = set(data) - {"id", "port", "data_dir", "database_url", "frontends"}
    if unknown:
        raise ValueError(f"Unknown workspace settings: {', '.join(sorted(unknown))}")
    ident = data.get("id", "")
    if not isinstance(ident, str) or not NAME.fullmatch(ident):
        raise ValueError("Workspace id must be a lowercase name, starting with a letter")
    if ident == "default":
        raise ValueError("The default workspace is reserved for the existing launch configuration")
    port = data.get("port", 8787)
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("Workspace port must be between 1024 and 65535")

    def local(value):
        if not isinstance(value, str) or not value:
            raise ValueError("Workspace paths must be nonempty strings")
        return (source.parent / Path(value).expanduser()).resolve()

    if "data_dir" not in data:
        raise ValueError("Named workspaces require an explicit data_dir")
    directory = local(data["data_dir"])
    database = data.get("database_url") or "sqlite:///" + str(directory / "gym.db")
    if not isinstance(database, str) or not database.startswith(("sqlite:///", "postgresql")):
        raise ValueError("Use a SQLite or PostgreSQL database URL")
    if database.startswith("sqlite:///") and not Path(database[10:]).is_absolute():
        database = "sqlite:///" + str(local(database[10:]))
    frontends = data.get("frontends", [])
    if not isinstance(frontends, list):
        raise ValueError("frontends must be a list of installed frontend directories")
    return Workspace(ident, port, directory, database, tuple(local(p) for p in frontends))
