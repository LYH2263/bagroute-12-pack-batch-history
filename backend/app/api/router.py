from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import BagItem, DeliveryRoute, PackBag, PackBatch, RejectRecord, SubscriberStop
from app.schemas.schemas import (
    BagItemOut,
    BagOut,
    BatchOut,
    PackRequest,
    PackResponse,
    RejectOut,
    RouteOut,
    StopOut,
    WeightOut,
)
from app.services.pack_engine import StopItem, pack_route

api_router = APIRouter()


def _latest_batch_id(db: Session) -> int | None:
    return db.scalar(select(func.max(PackBatch.id)))


def _resolve_batch_id(db: Session, batch_id: int | None) -> int | None:
    if batch_id is not None:
        if not db.get(PackBatch, batch_id):
            raise HTTPException(404, "批次不存在")
        return batch_id
    return _latest_batch_id(db)


def _bag_to_out(db: Session, b: PackBag) -> BagOut:
    items = db.scalars(select(BagItem).where(BagItem.bag_id == b.id)).all()
    return BagOut(
        id=b.id,
        batch_id=b.batch_id,
        route_id=b.route_id,
        bag_index=b.bag_index,
        weight_kg=b.weight_kg,
        volume_l=b.volume_l,
        items=[
            BagItemOut(
                stop_id=i.stop_id,
                stop_name=i.stop_name,
                weight_kg=i.weight_kg,
                volume_l=i.volume_l,
            )
            for i in items
        ],
    )


@api_router.get("/health")
def health():
    return {"status": "ok"}


@api_router.get("/routes", response_model=list[RouteOut])
def routes(db: Session = Depends(get_db)):
    return db.scalars(select(DeliveryRoute).order_by(DeliveryRoute.id)).all()


@api_router.get("/stops", response_model=list[StopOut])
def stops(route_id: int | None = None, db: Session = Depends(get_db)):
    q = select(SubscriberStop).order_by(SubscriberStop.route_id, SubscriberStop.seq)
    if route_id is not None:
        q = q.where(SubscriberStop.route_id == route_id)
    return db.scalars(q).all()


@api_router.get("/batches", response_model=list[BatchOut])
def batches(db: Session = Depends(get_db)):
    rows = db.scalars(select(PackBatch).order_by(PackBatch.id.desc())).all()
    bag_counts = dict(
        db.execute(
            select(PackBag.batch_id, func.count(PackBag.id)).group_by(PackBag.batch_id)
        ).all()
    )
    rej_counts = dict(
        db.execute(
            select(RejectRecord.batch_id, func.count(RejectRecord.id)).group_by(RejectRecord.batch_id)
        ).all()
    )
    return [
        BatchOut(
            id=b.id,
            route_id=b.route_id,
            bag_count=bag_counts.get(b.id, 0),
            reject_count=rej_counts.get(b.id, 0),
            created_at=b.created_at,
        )
        for b in rows
    ]


@api_router.post("/pack", response_model=PackResponse)
def pack(body: PackRequest, db: Session = Depends(get_db)):
    route = db.get(DeliveryRoute, body.route_id)
    if not route:
        raise HTTPException(404, "路线不存在")

    # 每次成功装袋生成新批次，历史批次袋明细与拒收保留可查
    batch = PackBatch(route_id=route.id)
    db.add(batch)
    db.flush()

    stops = db.scalars(
        select(SubscriberStop).where(SubscriberStop.route_id == route.id).order_by(SubscriberStop.seq)
    ).all()
    items = [
        StopItem(s.id, s.seq, s.weight_kg, s.volume_l, s.name) for s in stops
    ]
    result = pack_route(items, route.max_weight_kg, route.max_volume_l)
    out_bags: list[PackBag] = []
    for bag in result.bags:
        row = PackBag(
            batch_id=batch.id,
            route_id=route.id,
            bag_index=bag.bag_index,
            weight_kg=round(bag.weight_kg, 3),
            volume_l=round(bag.volume_l, 3),
        )
        db.add(row)
        db.flush()
        for it in bag.items:
            db.add(
                BagItem(
                    bag_id=row.id,
                    stop_id=it.stop_id,
                    stop_name=it.label,
                    weight_kg=it.weight_kg,
                    volume_l=it.volume_l,
                )
            )
        out_bags.append(row)
    for stop, reason in result.rejects:
        db.add(
            RejectRecord(
                batch_id=batch.id,
                route_id=route.id,
                stop_id=stop.stop_id,
                stop_name=stop.label,
                reason=reason,
            )
        )
    db.commit()
    return PackResponse(
        batch_id=batch.id,
        route_id=route.id,
        bag_count=len(out_bags),
        reject_count=len(result.rejects),
        bags=[_bag_to_out(db, b) for b in out_bags],
    )


@api_router.get("/bags", response_model=list[BagOut])
def bags(batch_id: int | None = None, db: Session = Depends(get_db)):
    bid = _resolve_batch_id(db, batch_id)
    if bid is None:
        return []
    rows = db.scalars(
        select(PackBag).where(PackBag.batch_id == bid).order_by(PackBag.bag_index)
    ).all()
    return [_bag_to_out(db, b) for b in rows]


@api_router.get("/rejects", response_model=list[RejectOut])
def rejects(batch_id: int | None = None, db: Session = Depends(get_db)):
    bid = _resolve_batch_id(db, batch_id)
    if bid is None:
        return []
    return db.scalars(
        select(RejectRecord)
        .where(RejectRecord.batch_id == bid)
        .order_by(RejectRecord.id.desc())
    ).all()


@api_router.get("/weights", response_model=list[WeightOut])
def weights(db: Session = Depends(get_db)):
    # 只展示最新批次，避免把历史袋算进当前仪表
    bid = _latest_batch_id(db)
    if bid is None:
        return []
    bags = db.scalars(
        select(PackBag).where(PackBag.batch_id == bid).order_by(PackBag.bag_index)
    ).all()
    out = []
    for b in bags:
        route = db.get(DeliveryRoute, b.route_id)
        assert route
        out.append(
            WeightOut(
                bag_id=b.id,
                batch_id=b.batch_id,
                bag_index=b.bag_index,
                route_id=b.route_id,
                weight_kg=b.weight_kg,
                volume_l=b.volume_l,
                fill_weight_pct=round(100 * b.weight_kg / route.max_weight_kg, 1),
                fill_volume_pct=round(100 * b.volume_l / route.max_volume_l, 1),
            )
        )
    return out
