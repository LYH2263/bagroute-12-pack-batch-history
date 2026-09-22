def _pack(client):
    r = client.post("/api/pack", json={"route_id": client.route_id})
    assert r.status_code == 200, r.text
    return r.json()


def test_consecutive_packs_keep_history_batches(client):
    first = _pack(client)
    second = _pack(client)

    # each successful pack generates a new, incrementing batch number
    assert second["batch_no"] == first["batch_no"] + 1
    assert second["batch_id"] != first["batch_id"]
    assert len(first["bags"]) == 2
    assert len(second["bags"]) == 2

    batches = client.get("/api/batches").json()
    assert [b["id"] for b in batches] == [second["batch_id"], first["batch_id"]]

    # default /bags shows the latest batch
    latest_bags = client.get("/api/bags").json()
    assert {b["batch_id"] for b in latest_bags} == {second["batch_id"]}
    assert len(latest_bags) == 2

    # the historical batch's bag detail is still queryable
    old_bags = client.get(f"/api/bags?batch_id={first['batch_id']}").json()
    assert len(old_bags) == 2
    assert {b["batch_id"] for b in old_bags} == {first["batch_id"]}
    # bag contents of the first run survived
    assert sorted(it["stop_name"] for b in old_bags for it in b["items"]) == ["乙", "甲"]


def test_rejects_remain_queryable_per_batch(client):
    first = _pack(client)
    second = _pack(client)

    # default rejects view = latest batch, still has the oversized stop
    latest_rj = client.get("/api/rejects").json()
    assert len(latest_rj) == 1
    assert latest_rj[0]["batch_id"] == second["batch_id"]
    assert latest_rj[0]["stop_name"] == "超大件"

    # old batch rejects retained and switchable
    old_rj = client.get(f"/api/rejects?batch_id={first['batch_id']}").json()
    assert len(old_rj) == 1
    assert old_rj[0]["batch_id"] == first["batch_id"]


def test_weights_only_cover_latest_batch_bag_count(client):
    _pack(client)
    second = _pack(client)

    weights = client.get("/api/weights").json()
    # one gauge row per bag of the latest batch only — historical bags excluded
    latest_bags = client.get("/api/bags").json()
    assert len(weights) == len(second["bags"]) == len(latest_bags) == 2
    assert {w["bag_id"] for w in weights} == {b["id"] for b in latest_bags}
    assert all(w["fill_weight_pct"] > 0 for w in weights)
