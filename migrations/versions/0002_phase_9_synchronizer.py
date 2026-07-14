"""create phase 9 synchronizer tables

Revision ID: 0002_phase_9_synchronizer
Revises: 0001_phase_7_memory
Create Date: 2026-07-14
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_phase_9_synchronizer"
down_revision = "0001_phase_7_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "synchronized_sources",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_key", sa.String(length=120), nullable=False, unique=True),
        sa.Column("region", sa.String(length=20), nullable=False),
        sa.Column("authority", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("local_path", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=20), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("etag", sa.String(length=255), nullable=True),
        sa.Column("last_modified", sa.String(length=255), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=True),
        sa.Column("content_length", sa.Integer(), nullable=True),
        sa.Column("document_id", sa.String(length=255), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_synchronized_sources_source_key", "synchronized_sources", ["source_key"])
    op.create_index("ix_synchronized_sources_region", "synchronized_sources", ["region"])
    op.create_index("ix_synchronized_sources_document_id", "synchronized_sources", ["document_id"])
    op.create_index("ix_synchronized_sources_status", "synchronized_sources", ["status"])

    op.create_table(
        "synchronization_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_scope", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("checked_count", sa.Integer(), nullable=False),
        sa.Column("unchanged_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("discovered_candidate_count", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
    )
    op.create_index("ix_synchronization_runs_status", "synchronization_runs", ["status"])

    op.create_table(
        "synchronization_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("synchronization_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.String(length=36), sa.ForeignKey("synchronized_sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("old_sha256", sa.String(length=64), nullable=True),
        sa.Column("new_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_synchronization_events_run_id", "synchronization_events", ["run_id"])
    op.create_index("ix_synchronization_events_source_id", "synchronization_events", ["source_id"])
    op.create_index("ix_synchronization_events_event_type", "synchronization_events", ["event_type"])

    op.create_table(
        "source_candidates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("discovered_from_source_id", sa.String(length=120), nullable=False),
        sa.Column("region", sa.String(length=20), nullable=False),
        sa.Column("candidate_url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("detected_title", sa.Text(), nullable=True),
        sa.Column("detected_content_type", sa.String(length=120), nullable=True),
        sa.Column("inferred_procedure_types_json", sa.JSON(), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=True),
        sa.Column("discovery_reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.UniqueConstraint("canonical_url", "region", name="uq_source_candidates_url_region"),
    )
    op.create_index("ix_source_candidates_discovered_from_source_id", "source_candidates", ["discovered_from_source_id"])
    op.create_index("ix_source_candidates_region", "source_candidates", ["region"])
    op.create_index("ix_source_candidates_status", "source_candidates", ["status"])


def downgrade() -> None:
    op.drop_index("ix_source_candidates_status", table_name="source_candidates")
    op.drop_index("ix_source_candidates_region", table_name="source_candidates")
    op.drop_index("ix_source_candidates_discovered_from_source_id", table_name="source_candidates")
    op.drop_table("source_candidates")
    op.drop_index("ix_synchronization_events_event_type", table_name="synchronization_events")
    op.drop_index("ix_synchronization_events_source_id", table_name="synchronization_events")
    op.drop_index("ix_synchronization_events_run_id", table_name="synchronization_events")
    op.drop_table("synchronization_events")
    op.drop_index("ix_synchronization_runs_status", table_name="synchronization_runs")
    op.drop_table("synchronization_runs")
    op.drop_index("ix_synchronized_sources_status", table_name="synchronized_sources")
    op.drop_index("ix_synchronized_sources_document_id", table_name="synchronized_sources")
    op.drop_index("ix_synchronized_sources_region", table_name="synchronized_sources")
    op.drop_index("ix_synchronized_sources_source_key", table_name="synchronized_sources")
    op.drop_table("synchronized_sources")
