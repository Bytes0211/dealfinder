"""Initial schema for Deal Finder.

Revision ID: 001
Revises: None
Create Date: 2026-02-17

Creates the following tables:
- deal_sources: RSS feed sources
- deals: Discovered deals
- users: User accounts
- price_estimates: ML model predictions
- notifications: Notification history
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables."""
    # Create enum types
    op.execute("CREATE TYPE dealstatus AS ENUM ('discovered', 'evaluating', 'evaluated', 'notified', 'expired', 'rejected')")
    op.execute("CREATE TYPE notificationchannel AS ENUM ('email', 'pushover', 'sms', 'websocket')")
    op.execute("CREATE TYPE notificationstatus AS ENUM ('pending', 'sent', 'delivered', 'failed')")

    # Create deal_sources table
    op.create_table(
        "deal_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False, unique=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("check_interval_minutes", sa.Integer(), default=15),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_successful_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_count", sa.Integer(), default=0),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_deal_sources_is_active", "deal_sources", ["is_active"])
    op.create_index("ix_deal_sources_category", "deal_sources", ["category"])

    # Create deals table
    op.create_table(
        "deals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deal_sources.id"), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("original_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("sale_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("discount_percentage", sa.Numeric(5, 2), nullable=True),
        sa.Column("currency", sa.String(3), default="USD"),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("brand", sa.String(255), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
        sa.Column("status", postgresql.ENUM("discovered", "evaluating", "evaluated", "notified", "expired", "rejected", name="dealstatus", create_type=False), default="discovered"),
        sa.Column("confidence_score", sa.Numeric(4, 3), nullable=True),
        sa.Column("is_high_value", sa.Boolean(), default=False),
        sa.Column("embedding_id", sa.String(255), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("raw_data", postgresql.JSONB(), nullable=True),
    )
    op.create_unique_constraint("uq_deals_source_external", "deals", ["source_id", "external_id"])
    op.create_index("ix_deals_status", "deals", ["status"])
    op.create_index("ix_deals_is_high_value", "deals", ["is_high_value"])
    op.create_index("ix_deals_discovered_at", "deals", ["discovered_at"])
    op.create_index("ix_deals_category", "deals", ["category"])
    op.create_index("ix_deals_discount_percentage", "deals", ["discount_percentage"])

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("is_verified", sa.Boolean(), default=False),
        sa.Column("notification_preferences", postgresql.JSONB(), nullable=True),
        sa.Column("discount_threshold", sa.Numeric(5, 2), default=20.00),
        sa.Column("preferred_categories", postgresql.JSONB(), nullable=True),
        sa.Column("pushover_user_key", sa.String(255), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_is_active", "users", ["is_active"])

    # Create price_estimates table
    op.create_table(
        "price_estimates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("estimated_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("prediction_range_low", sa.Numeric(12, 2), nullable=True),
        sa.Column("prediction_range_high", sa.Numeric(12, 2), nullable=True),
        sa.Column("ensemble_weight", sa.Numeric(4, 3), nullable=True),
        sa.Column("is_ensemble_member", sa.Boolean(), default=True),
        sa.Column("inference_time_ms", sa.Integer(), nullable=True),
        sa.Column("features_used", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_price_estimates_deal_id", "price_estimates", ["deal_id"])
    op.create_index("ix_price_estimates_model_name", "price_estimates", ["model_name"])
    op.create_unique_constraint("uq_price_estimates_deal_model", "price_estimates", ["deal_id", "model_name", "model_version"])

    # Create notifications table
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("deal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", postgresql.ENUM("email", "pushover", "sms", "websocket", name="notificationchannel", create_type=False), nullable=False),
        sa.Column("status", postgresql.ENUM("pending", "sent", "delivered", "failed", name="notificationstatus", create_type=False), default="pending"),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), default=0),
        sa.Column("external_message_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_deal_id", "notifications", ["deal_id"])
    op.create_index("ix_notifications_status", "notifications", ["status"])
    op.create_index("ix_notifications_channel", "notifications", ["channel"])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("notifications")
    op.drop_table("price_estimates")
    op.drop_table("users")
    op.drop_table("deals")
    op.drop_table("deal_sources")
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS notificationstatus")
    op.execute("DROP TYPE IF EXISTS notificationchannel")
    op.execute("DROP TYPE IF EXISTS dealstatus")
