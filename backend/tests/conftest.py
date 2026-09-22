import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite://")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import DeliveryRoute, SubscriberStop


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSession()
    # Route where one stop is oversized -> a reject on every pack, and packing
    # produces two bags.
    route = DeliveryRoute(name="测试线", max_weight_kg=5.0, max_volume_l=10.0)
    db.add(route)
    db.flush()
    db.add_all(
        [
            SubscriberStop(route_id=route.id, seq=1, name="甲", weight_kg=3.0, volume_l=4.0),
            SubscriberStop(route_id=route.id, seq=2, name="乙", weight_kg=3.0, volume_l=4.0),
            SubscriberStop(route_id=route.id, seq=3, name="超大件", weight_kg=9.0, volume_l=1.0),
        ]
    )
    db.commit()
    route_id = route.id
    db.close()

    def override_get_db():
        s = TestingSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    # Plain TestClient (no context manager) so the lifespan — which runs the
    # Postgres-backed batch migration against the real engine — does not fire.
    # The schema is created above on the test engine instead.
    c = TestClient(app)
    c.route_id = route_id  # type: ignore[attr-defined]
    yield c
    app.dependency_overrides.clear()
