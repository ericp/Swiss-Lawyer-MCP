"""create phase 7 memory tables

Revision ID: 0001_phase_7_memory
Revises:
Create Date: 2026-07-10
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_phase_7_memory"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("external_user_key", sa.String(length=255), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "user_profile_facts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("is_confirmed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "field_name", name="uq_user_profile_facts_user_field"),
    )
    op.create_index("ix_user_profile_facts_user_id", "user_profile_facts", ["user_id"])

    op.create_table(
        "procedures",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("intent", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_procedures_user_id", "procedures", ["user_id"])
    op.create_index("ix_procedures_intent", "procedures", ["intent"])
    op.create_index("ix_procedures_status", "procedures", ["status"])

    op.create_table(
        "procedure_interactions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("procedure_id", sa.String(length=36), sa.ForeignKey("procedures.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interaction_type", sa.String(length=80), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("structured_payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_procedure_interactions_procedure_id", "procedure_interactions", ["procedure_id"])
    op.create_index("ix_procedure_interactions_interaction_type", "procedure_interactions", ["interaction_type"])


def downgrade() -> None:
    op.drop_index("ix_procedure_interactions_interaction_type", table_name="procedure_interactions")
    op.drop_index("ix_procedure_interactions_procedure_id", table_name="procedure_interactions")
    op.drop_table("procedure_interactions")
    op.drop_index("ix_procedures_status", table_name="procedures")
    op.drop_index("ix_procedures_intent", table_name="procedures")
    op.drop_index("ix_procedures_user_id", table_name="procedures")
    op.drop_table("procedures")
    op.drop_index("ix_user_profile_facts_user_id", table_name="user_profile_facts")
    op.drop_table("user_profile_facts")
    op.drop_table("users")
