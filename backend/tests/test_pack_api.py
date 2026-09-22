import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import DeliveryRoute, PackBag, RejectRecord, SubscriberStop


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    db = TestingSession()
    route = DeliveryRoute(name="测试线", max_weight_kg=8.0, max_volume_l=18.0)
    db.add(route)
    db.flush()
    # seq=4 is oversized on the first run; the test shrinks it before run 2
    db.add_all(
        [
            SubscriberStop(route_id=route.id, seq=1, name="甲", weight_kg=2.2, volume_l=4.0),
            SubscriberStop(route_id=route.id, seq=2, name="乙", weight_kg=3.5, volume_l=5.5),
            SubscriberStop(route_id=route.id, seq=3, name="丙", weight_kg=6.0, volume_l=3.0),
            SubscriberStop(route_id=route.id, seq=4, name="超大件", weight_kg=9.5, volume_l=6.0),
        ]
    )
    db.commit()
    route_id = route.id
    db.close()

    # Plain TestClient (no context manager) so the lifespan that touches the
    # real configured engine does not run; the fixture creates the SQLite
    # schema itself and overrides the get_db dependency.
    c = TestClient(app)
    yield c, TestingSession, route_id

    app.dependency_overrides.clear()


def test_consecutive_packs_keep_history_and_weights_match_latest(client):
    c, SessionLocal, route_id = client

    # 第一次装袋：甲+乙同袋、丙单独成袋，超大件拒收 -> 2 袋 1 拒收
    r1 = c.post("/api/pack", json={"route_id": route_id})
    assert r1.status_code == 200
    p1 = r1.json()
    assert p1["batch_id"] == 1
    assert p1["bag_count"] == 2
    assert p1["reject_count"] == 1
    first_bag_count = p1["bag_count"]

    # 把超大件改小后再次装袋：丁件装不进丙袋，多出一袋 -> 3 袋，无拒收
    db = SessionLocal()
    over = db.scalar(select(SubscriberStop).where(SubscriberStop.name == "超大件"))
    over.weight_kg = 2.5
    over.volume_l = 4.0
    db.commit()
    db.close()

    r2 = c.post("/api/pack", json={"route_id": route_id})
    assert r2.status_code == 200
    p2 = r2.json()
    assert p2["batch_id"] == 2
    assert p2["reject_count"] == 0
    latest_bag_count = p2["bag_count"]

    # 两次生成不同批次，批次列表均在
    batches = c.get("/api/batches").json()
    assert [b["id"] for b in batches] == [2, 1]
    assert {b["bag_count"] for b in batches} == {first_bag_count, latest_bag_count}

    # 历史批次袋明细仍可查；默认返回最新批次
    old_bags = c.get("/api/bags?batch_id=1").json()
    assert len(old_bags) == first_bag_count
    assert all(b["batch_id"] == 1 for b in old_bags)
    assert [b["id"] for b in c.get("/api/bags").json()][0:1]  # non-empty
    assert all(b["batch_id"] == 2 for b in c.get("/api/bags").json())

    # 历史批次拒收仍可查；最新批次无拒收
    old_rej = c.get("/api/rejects?batch_id=1").json()
    assert len(old_rej) == 1
    assert old_rej[0]["batch_id"] == 1
    assert old_rej[0]["stop_name"] == "超大件"
    assert c.get("/api/rejects").json() == []

    # 袋重条数等于最新批次袋数，且全部来自最新批次
    weights = c.get("/api/weights").json()
    assert len(weights) == latest_bag_count
    assert all(w["batch_id"] == 2 for w in weights)
    assert [w["bag_index"] for w in weights] == sorted(w["bag_index"] for w in weights)

    # 数据库层：历史行未被清空
    db = SessionLocal()
    assert db.scalar(select(PackBag).where(PackBag.batch_id == 1)) is not None
    assert db.scalar(select(RejectRecord).where(RejectRecord.batch_id == 1)) is not None
    assert len(db.scalars(select(PackBag)).all()) == first_bag_count + latest_bag_count
    db.close()


def test_empty_state_before_any_pack(client):
    c, _SessionLocal, _route_id = client
    assert c.get("/api/bags").json() == []
    assert c.get("/api/rejects").json() == []
    assert c.get("/api/weights").json() == []
    assert c.get("/api/batches").json() == []


def test_unknown_batch_and_route_404(client):
    c, _SessionLocal, route_id = client
    c.post("/api/pack", json={"route_id": route_id})
    assert c.get("/api/bags?batch_id=999").status_code == 404
    assert c.post("/api/pack", json={"route_id": 9999}).status_code == 404
