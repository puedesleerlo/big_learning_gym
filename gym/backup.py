"""Portable, checksummed workspace snapshots; credentials are never part of the archive."""

import hashlib
import json
import os
import zipfile
from pathlib import Path

from sqlalchemy import delete, insert, select

from .store import metadata, now, records


def backup(store, destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Choose a new backup filename")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # The same transaction lock used by all mutations gives one coherent database snapshot.
    with store.tx() as c:
        tables = {t.name: [dict(r) for r in c.execute(select(t)).mappings()] for t in metadata.sorted_tables}
        files = {}
        for row in tables["records"]:
            if row["kind"] == "source":
                path = Path(row["data"]["storage_path"])
                raw = path.read_bytes()
                name = "files/" + hashlib.sha256(raw).hexdigest() + path.suffix
                files[name] = raw
                row["data"] = {**row["data"], "storage_path": name}
        snapshot = json.dumps({"version": 1, "created_at": now(), "tables": tables}).encode()
        files["workspace.json"] = snapshot
        manifest = json.dumps({name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}).encode()
        # Open with exclusive creation and restrictive permissions, including on the first write.
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as output, zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, raw in files.items():
                archive.writestr(name, raw)
            archive.writestr("manifest.json", manifest)
    return {"path": str(destination.resolve()), "files": len(files) - 1, "records": len(tables["records"])}


def restore(store, source):
    with zipfile.ZipFile(source) as archive:
        if sum(x.file_size for x in archive.infolist()) > 2_000_000_000:
            raise ValueError("Backup exceeds the 2 GB restore limit")
        manifest = json.loads(archive.read("manifest.json"))
        if set(archive.namelist()) != set(manifest) | {"manifest.json"}:
            raise ValueError("Unexpected backup members")
        contents = {}
        for name, checksum in manifest.items():
            if name != "workspace.json" and (not name.startswith("files/") or len(Path(name).parts) != 2):
                raise ValueError("Invalid backup path")
            raw = archive.read(name)
            if hashlib.sha256(raw).hexdigest() != checksum:
                raise ValueError("Backup checksum mismatch")
            contents[name] = raw
        snapshot = json.loads(contents["workspace.json"])
        if snapshot["version"] != 1 or set(snapshot["tables"]) != set(metadata.tables):
            raise ValueError("Unsupported backup schema")
    with store.tx() as c:
        existing = c.execute(select(records).where(records.c.kind != "model")).first()
        if existing:
            raise ValueError("Restore requires an empty workspace; use a new database and data directory")
        for row in snapshot["tables"]["records"]:
            if row["kind"] == "source":
                name = row["data"]["storage_path"]
                if name not in contents or not name.startswith("files/"):
                    raise ValueError("Missing source file")
                destination = store.data_dir / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(contents[name])
                row["data"]["storage_path"] = str(destination.resolve())
        for job in snapshot["tables"]["jobs"]:
            if job["status"] == "running":
                job.update(status="queued", lease_until=None, lease_token=None)
        for table in reversed(metadata.sorted_tables):
            c.execute(delete(table))
        for table in metadata.sorted_tables:
            rows = snapshot["tables"][table.name]
            if rows:
                c.execute(insert(table), rows)
    return {"restored_records": len(snapshot["tables"]["records"]), "created_at": snapshot["created_at"]}
