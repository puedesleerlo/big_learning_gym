import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from gym.api import create_app
from gym.store import Store


@pytest.fixture
def store(tmp_path):
    postgres = os.getenv("GYM_TEST_DATABASE_URL")
    schema = "test_" + uuid.uuid4().hex
    engine = create_engine(postgres) if postgres else None
    if engine:
        with engine.begin() as c:
            c.exec_driver_sql(f"CREATE SCHEMA {schema}")
    result = Store(
        postgres + f"?options=-csearch_path%3D{schema}"
        if postgres
        else "sqlite:///" + str(tmp_path / "test.db"),
        tmp_path,
    )
    with result.tx() as c:
        result.put(c, "course", "course", {"title": "Test gym", "description": "Test course", "modules": []})
    yield result
    result.engine.dispose()
    if engine:
        with engine.begin() as c:
            c.exec_driver_sql(f"DROP SCHEMA {schema} CASCADE")
        engine.dispose()


@pytest.fixture
def client(store):
    with TestClient(create_app(store, embedded_worker=False)) as client:
        yield client


@pytest.fixture
def item(store):
    data = {
        "course_id": "course",
        "module": "reasoning",
        "type": "mcq",
        "pool": "practice",
        "status": "active",
        "stem": "Which conclusion follows from this randomized comparison?",
        "points": 5,
        "options": [
            {"label": x, "text": "Option " + x, "correct": x == "B", "why": "Explanation for " + x}
            for x in "ABCD"
        ],
        "key": "B",
        "explanation": "B follows under the stated assignment and observation assumptions.",
        "hint": "Check the assignment mechanism",
        "plain": {"stem": "What can you infer from this experiment?"},
        "capabilities": ["reasoning"],
        "family_id": "family1",
        "cognitive_operation": "application",
        "rubric_version": "v1",
    }
    with store.tx() as c:
        return store.put(c, "item", "item", data)
