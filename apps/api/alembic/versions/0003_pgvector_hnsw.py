"""0003_pgvector_hnsw

pgvector HNSW index creation on note_chunks with cosine distance
metric and runtime ef_search configuration.

Revision ID: 0003_pgvector_hnsw
Revises: 0002_rls_policies
Create Date: 2026-09-11 10:20:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = "0003_pgvector_hnsw"
down_revision: Union[str, None] = "0002_rls_policies"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. HNSW Index for vector cosine similarity search (OpenAI 1536 dim)
    op.execute("""
        CREATE INDEX idx_note_chunks_embedding_hnsw
        ON note_chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)

    # 2. Recommended session / transaction search quality parameter
    op.execute("SET hnsw.ef_search = 40;")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_note_chunks_embedding_hnsw;")
