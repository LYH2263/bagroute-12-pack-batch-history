"""Lightweight startup migrations for existing deployments.

The project uses Base.metadata.create_all (no Alembic). When the batch
concept was introduced, old databases already had pack_bags /
reject_records rows without a batch_id. We add the columns in place and
attach every legacy row to a per-route "legacy" batch so history stays
visible. Idempotent: a fresh schema already has the columns.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _has_column(inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def run_lightweight_migrations(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "pack_bags" not in tables or "reject_records" not in tables:
        return

    add_bag_col = not _has_column(inspector, "pack_bags", "batch_id")
    add_rej_col = not _has_column(inspector, "reject_records", "batch_id")

    with engine.begin() as conn:
        if add_bag_col:
            conn.execute(text("ALTER TABLE pack_bags ADD COLUMN batch_id INTEGER"))
        if add_rej_col:
            conn.execute(text("ALTER TABLE reject_records ADD COLUMN batch_id INTEGER"))

        # Backfill any rows still missing a batch (legacy rows, or a previous
        # startup that was interrupted mid-migration). No-op when everything
        # is already linked: one legacy batch per route that ever had rows.
        conn.execute(
            text(
                """
                INSERT INTO pack_batches (route_id, created_at)
                SELECT DISTINCT route_id, CURRENT_TIMESTAMP FROM (
                    SELECT route_id FROM pack_bags WHERE batch_id IS NULL
                    UNION
                    SELECT route_id FROM reject_records WHERE batch_id IS NULL
                ) AS legacy_routes
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE pack_bags
                   SET batch_id = (
                        SELECT pb.id FROM pack_batches pb
                        WHERE pb.route_id = pack_bags.route_id
                        ORDER BY pb.id LIMIT 1
                   )
                 WHERE batch_id IS NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE reject_records
                   SET batch_id = (
                        SELECT pb.id FROM pack_batches pb
                        WHERE pb.route_id = reject_records.route_id
                        ORDER BY pb.id LIMIT 1
                   )
                 WHERE batch_id IS NULL
                """
            )
        )
