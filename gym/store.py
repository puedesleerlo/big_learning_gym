"""Transactional storage. Evidence, predictions and decisions are separate memories.

Records are current-state projections; they may be replaced. Evidence is append-oriented.
Every mutation and its durable outgoing job are committed in the same transaction.
"""

import hashlib
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    JSON,
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
    insert,
    inspect,
    select,
    update,
)


def now():
    return datetime.now(timezone.utc).isoformat()


def uid(prefix=""):
    return prefix + uuid.uuid4().hex


def digest(value):
    raw = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


metadata = MetaData()
state = Table(
    "system_state",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("revision", Integer, nullable=False),
    Column("schema_version", Integer, nullable=False),
)
records = Table(
    "records",
    metadata,
    Column("id", String, primary_key=True),
    Column("kind", String, index=True, primary_key=True),
    Column("revision", Integer, nullable=False),
    Column("data", JSON, nullable=False),
    Column("updated_at", String, nullable=False),
)
events = Table(
    "evidence_events",
    metadata,
    Column("id", String, primary_key=True),
    Column("idempotency_key", String, unique=True, nullable=False),
    Column("event_type", String, index=True, nullable=False),
    Column("entity_id", String, index=True),
    Column("occurred_at", String, nullable=False),
    Column("received_at", String, nullable=False),
    Column("source_id", String),
    Column("source_revision", String),
    Column("supersedes_event_id", String),
    Column("payload", JSON, nullable=False),
    Column("quality_flags", JSON, nullable=False),
)
predictions = Table(
    "predictions",
    metadata,
    Column("id", String, primary_key=True),
    Column("target_id", String, index=True, nullable=False),
    Column("target_version", Integer),
    Column("quantity", String, nullable=False),
    Column("distribution", JSON, nullable=False),
    Column("input_state_revision", Integer, nullable=False),
    Column("input_evidence_ids", JSON),
    Column("model_version", String, nullable=False),
    Column("created_at", String, nullable=False),
    Column("stale_reason", String),
    Column("dependencies", JSON, nullable=False),
)
decisions = Table(
    "decisions",
    metadata,
    Column("id", String, primary_key=True),
    Column("decision_type", String, nullable=False),
    Column("input_state_revision", Integer),
    Column("prediction_ids", JSON),
    Column("proposed_action", JSON, nullable=False),
    Column("alternatives", JSON),
    Column("rationale", Text),
    Column("policy_version", String),
    Column("approval_status", String),
    Column("execution_status", String),
    Column("created_at", String, nullable=False),
)
jobs = Table(
    "jobs",
    metadata,
    Column("id", String, primary_key=True),
    Column("idempotency_key", String, unique=True, nullable=False),
    Column("kind", String),
    Column("payload", JSON),
    Column("priority", Integer),
    Column("status", String, index=True),
    Column("attempts", Integer),
    Column("max_attempts", Integer),
    Column("run_at", Float),
    Column("lease_until", Float),
    Column("lease_token", String),
    Column("last_error", Text),
    Column("created_at", String),
    Column("finished_at", String),
)
llm_calls = Table(
    "llm_calls",
    metadata,
    Column("id", String, primary_key=True),
    Column("role", String),
    Column("provider", String),
    Column("model", String),
    Column("config_hash", String),
    Column("prompt_hash", String),
    Column("status", String),
    Column("usage", JSON),
    Column("elapsed_seconds", Float),
    Column("created_at", String),
)


class Store:
    def __init__(self, url=None, data_dir=None):
        self.data_dir = Path(data_dir or os.getenv("GYM_DATA_DIR", "data"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.url = url or os.getenv("GYM_DATABASE_URL", "sqlite:///data/gym.db")
        kwargs = (
            {"connect_args": {"check_same_thread": False, "timeout": 30}}
            if self.url.startswith("sqlite")
            else {}
        )
        self.engine = create_engine(self.url, **kwargs)
        if self.url.startswith("sqlite"):

            @event.listens_for(self.engine, "connect")
            def sqlite_setup(conn, _):
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA foreign_keys=ON")

        metadata.create_all(self.engine)
        # Schema v2 scopes identity by record type (a draft and its assignment share an id).
        if inspect(self.engine).get_pk_constraint("records")["constrained_columns"] == ["id"]:
            with self.engine.begin() as c:
                c.exec_driver_sql(
                    "CREATE TABLE records_v2 (id VARCHAR NOT NULL, kind VARCHAR NOT NULL, revision INTEGER NOT NULL, data JSON NOT NULL, updated_at VARCHAR NOT NULL, PRIMARY KEY (id,kind))"
                )
                c.exec_driver_sql(
                    "INSERT INTO records_v2 SELECT id,kind,revision,data,updated_at FROM records"
                )
                c.exec_driver_sql("DROP TABLE records")
                c.exec_driver_sql("ALTER TABLE records_v2 RENAME TO records")
                c.exec_driver_sql("CREATE INDEX ix_records_kind ON records (kind)")
        with self.tx() as c:
            if not c.execute(select(state)).first():
                c.execute(insert(state).values(id=1, revision=0, schema_version=2))
            else:
                c.execute(update(state).where(state.c.id == 1).values(schema_version=2))
            if not self.get(c, "model", "effort-prior-v1", False):
                self.put(
                    c,
                    "model",
                    "effort-prior-v1",
                    {
                        "role": "effort",
                        "status": "active",
                        "multiplier": 1.0,
                        "upper_multiplier": 1.4,
                        "promotion_eligible": True,
                        "created_at": now(),
                        "baseline": True,
                    },
                )

    @contextmanager
    def tx(self):
        with self.engine.connect() as c:
            if self.engine.dialect.name == "sqlite":
                c.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                c.begin()
                # One-person state transitions are serialized across API and worker.
                c.execute(select(state).where(state.c.id == 1).with_for_update())
            try:
                yield c
                c.commit()
            except BaseException:
                c.rollback()
                raise

    def revision(self, c):
        return c.execute(select(state.c.revision).where(state.c.id == 1)).scalar_one()

    def bump(self, c):
        c.execute(update(state).where(state.c.id == 1).values(revision=state.c.revision + 1))
        return self.revision(c)

    def get(self, c, kind, ident, required=True):
        r = c.execute(select(records).where(records.c.id == ident, records.c.kind == kind)).mappings().first()
        if not r:
            if required:
                raise ValueError(f"{kind} not found: {ident}")
            return None
        return {**r["data"], "id": r["id"], "revision": r["revision"]}

    def list(self, c, kind):
        return [
            {**r["data"], "id": r["id"], "revision": r["revision"]}
            for r in c.execute(
                select(records).where(records.c.kind == kind).order_by(records.c.updated_at)
            ).mappings()
        ]

    def put(self, c, kind, ident, data, expected_revision=None):
        old = self.get(c, kind, ident, required=False)
        if expected_revision is not None and (not old or old["revision"] != expected_revision):
            raise ValueError("This record changed. Reload before saving.")
        data = {k: v for k, v in data.items() if k not in {"id", "revision"}}
        revision = (old["revision"] if old else 0) + 1
        values = dict(kind=kind, revision=revision, data=data, updated_at=now())
        if old:
            c.execute(update(records).where(records.c.id == ident, records.c.kind == kind).values(**values))
        else:
            c.execute(insert(records).values(id=ident, **values))
        return {**data, "id": ident, "revision": revision}

    def emit(
        self,
        c,
        event_type,
        entity_id,
        payload,
        key=None,
        occurred_at=None,
        source_id=None,
        source_revision=None,
        supersedes=None,
        quality_flags=None,
    ):
        key = key or uid("event:")
        previous = c.execute(select(events.c.id).where(events.c.idempotency_key == key)).scalar()
        if previous:
            return previous, False
        ident = uid("ev_")
        c.execute(
            insert(events).values(
                id=ident,
                event_type=event_type,
                entity_id=entity_id,
                idempotency_key=key,
                occurred_at=occurred_at or now(),
                received_at=now(),
                payload=payload,
                source_id=source_id,
                source_revision=source_revision,
                supersedes_event_id=supersedes,
                quality_flags=quality_flags or [],
            )
        )
        self.bump(c)
        self.enqueue(c, "operational", {"event_id": ident}, key="operational:" + ident)
        return ident, True

    def enqueue(self, c, kind, payload, key=None, priority=20, delay=0):
        import time

        key = key or uid("job:")
        old = c.execute(select(jobs.c.id).where(jobs.c.idempotency_key == key)).scalar()
        if old:
            return old
        ident = uid("job_")
        c.execute(
            insert(jobs).values(
                id=ident,
                idempotency_key=key,
                kind=kind,
                payload=payload,
                priority=priority,
                status="queued",
                attempts=0,
                max_attempts=3,
                run_at=time.time() + delay,
                lease_until=0,
                created_at=now(),
            )
        )
        return ident

    def invalidate(self, c, dependency, reason):
        affected = []
        for p in c.execute(select(predictions).where(predictions.c.stale_reason.is_(None))).mappings():
            if dependency in p["dependencies"]:
                c.execute(update(predictions).where(predictions.c.id == p["id"]).values(stale_reason=reason))
                affected.append(p["target_id"])
        return affected

    def evidence(self, c, entity_id=None, limit=100):
        q = select(events).order_by(events.c.received_at.desc()).limit(limit)
        if entity_id:
            q = q.where(events.c.entity_id == entity_id)
        return [dict(r) for r in c.execute(q).mappings()]
