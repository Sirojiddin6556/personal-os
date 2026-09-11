"""0004_partitioned_activity_audit

Partitioning implementation for high-volume logs:
activity_events and audit_logs RANGE partitioned monthly by occurred_at,
default safety catch-all partitions, partition indexes, and outbox retention procedure.

Revision ID: 0004_partitioned_activity_audit
Revises: 0003_pgvector_hnsw
Create Date: 2026-09-11 10:30:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0004_partitioned_activity_audit"
down_revision: Union[str, None] = "0003_pgvector_hnsw"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MONTHS = [
    ("y2026m09", "2026-09-01 00:00:00+00", "2026-10-01 00:00:00+00"),
    ("y2026m10", "2026-10-01 00:00:00+00", "2026-11-01 00:00:00+00"),
    ("y2026m11", "2026-11-01 00:00:00+00", "2026-12-01 00:00:00+00"),
    ("y2026m12", "2026-12-01 00:00:00+00", "2027-01-01 00:00:00+00"),
    ("y2027m01", "2027-01-01 00:00:00+00", "2027-02-01 00:00:00+00"),
    ("y2027m02", "2027-02-01 00:00:00+00", "2027-03-01 00:00:00+00"),
]


def upgrade() -> None:
    # 1. Partitions for activity_events
    for suffix, start_ts, end_ts in MONTHS:
        op.execute(f"""
            CREATE TABLE IF NOT EXISTS activity_events_{suffix} PARTITION OF activity_events
            FOR VALUES FROM ('{start_ts}') TO ('{end_ts}');
        """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS activity_events_default PARTITION OF activity_events DEFAULT;
    """)

    # 2. Partitions for audit_logs
    for suffix, start_ts, end_ts in MONTHS:
        op.execute(f"""
            CREATE TABLE IF NOT EXISTS audit_logs_{suffix} PARTITION OF audit_logs
            FOR VALUES FROM ('{start_ts}') TO ('{end_ts}');
        """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs_default PARTITION OF audit_logs DEFAULT;
    """)

    # 3. Composite indexes on partitioned tables (propagated to child partitions)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_activity_events_workspace_occurred 
        ON activity_events (workspace_id, occurred_at DESC);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_activity_events_aggregate 
        ON activity_events (workspace_id, aggregate_type, aggregate_id);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_logs_workspace_occurred 
        ON audit_logs (workspace_id, occurred_at DESC);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_logs_actor 
        ON audit_logs (workspace_id, actor_id, occurred_at DESC);
    """)

    # 4. Stored procedure for scheduled Outbox retention purge
    op.execute("""
        CREATE OR REPLACE PROCEDURE purge_published_outbox_events(batch_size INT DEFAULT 5000)
        AS $$
        DECLARE
            rows_deleted INT;
        BEGIN
            LOOP
                DELETE FROM outbox_events
                WHERE id IN (
                    SELECT id 
                    FROM outbox_events 
                    WHERE status = 'published' 
                      AND published_at < clock_timestamp() - INTERVAL '24 hours'
                    LIMIT batch_size
                );
                GET DIAGNOSTICS rows_deleted = ROW_COUNT;
                EXIT WHEN rows_deleted = 0;
                COMMIT;
            END LOOP;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    op.execute("DROP PROCEDURE IF EXISTS purge_published_outbox_events(INT);")

    op.execute("DROP INDEX IF EXISTS idx_audit_logs_actor;")
    op.execute("DROP INDEX IF EXISTS idx_audit_logs_workspace_occurred;")
    op.execute("DROP INDEX IF EXISTS idx_activity_events_aggregate;")
    op.execute("DROP INDEX IF EXISTS idx_activity_events_workspace_occurred;")

    op.execute("DROP TABLE IF EXISTS audit_logs_default;")
    for suffix, _, _ in MONTHS:
        op.execute(f"DROP TABLE IF EXISTS audit_logs_{suffix};")

    op.execute("DROP TABLE IF EXISTS activity_events_default;")
    for suffix, _, _ in MONTHS:
        op.execute(f"DROP TABLE IF EXISTS activity_events_{suffix};")
