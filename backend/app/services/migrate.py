"""Idempotent lightweight migration for the batch feature.

The project creates schema with ``Base.metadata.create_all`` (no Alembic), so an
existing database keeps the old ``pack_bags`` / ``reject_records`` tables without
the new ``batch_id`` column. This adds the columns and groups pre-existing rows
into one backfilled batch per route. Safe to run on every startup.
"""

from __future__ import annotations

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.database import engine
from app.models.models import PackBag, PackBatch, RejectRecord


def _has_column(insp, table: str, column: str) -> bool:
    return column in {c["name"] for c in insp.get_columns(table)}


def run_batch_migration() -> None:
    insp = inspect(engine)
    if "pack_bags" not in insp.get_table_names():
        return  # fresh database; create_all already built the full schema

    with engine.begin() as conn:
        if not _has_column(insp, "pack_bags", "batch_id"):
            conn.execute(text("ALTER TABLE pack_bags ADD COLUMN batch_id INTEGER"))
        if not _has_column(insp, "reject_records", "batch_id"):
            conn.execute(text("ALTER TABLE reject_records ADD COLUMN batch_id INTEGER"))

    # Backfill one batch per route for any rows left without one.
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        bag_routes = {r for (r,) in db.execute(select(PackBag.route_id).where(PackBag.batch_id.is_(None))).all()}
        rej_routes = {r for (r,) in db.execute(select(RejectRecord.route_id).where(RejectRecord.batch_id.is_(None))).all()}
        for route_id in bag_routes | rej_routes:
            last_no = db.scalar(
                select(PackBatch.batch_no)
                .where(PackBatch.route_id == route_id)
                .order_by(PackBatch.batch_no.desc())
                .limit(1)
            )
            batch = PackBatch(route_id=route_id, batch_no=(last_no or 0) + 1)
            db.add(batch)
            db.flush()
            db.query(PackBag).filter(
                PackBag.route_id == route_id, PackBag.batch_id.is_(None)
            ).update({PackBag.batch_id: batch.id}, synchronize_session=False)
            db.query(RejectRecord).filter(
                RejectRecord.route_id == route_id, RejectRecord.batch_id.is_(None)
            ).update({RejectRecord.batch_id: batch.id}, synchronize_session=False)
        db.commit()
    finally:
        db.close()
