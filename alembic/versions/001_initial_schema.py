"""initial schema (subscriber-only syndication)

Revision ID: 001
Revises:
Create Date: 2026-06-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("setup_state", sa.String(32), nullable=False, server_default="awaiting_supergroup"),
        sa.Column("feed_supergroup_id", sa.BigInteger()),
        sa.Column("topic_newest_id", sa.Integer()),
        sa.Column("topic_popular_id", sa.Integer()),
        sa.Column("topic_foryou_id", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table(
        "participating_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(64)),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("owner_user_id", sa.BigInteger()),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_participating_channels_chat_id", "participating_channels", ["chat_id"], unique=True)
    op.create_index("ix_participating_channels_status", "participating_channels", ["status"])

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("participating_channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("added_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default="false"),
        sa.UniqueConstraint("user_id", "channel_id", name="uq_subscription_user_channel"),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("ix_subscriptions_channel_id", "subscriptions", ["channel_id"])

    op.create_table(
        "channel_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_id", sa.Integer(), sa.ForeignKey("participating_channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("text_preview", sa.Text()),
        sa.Column("media_type", sa.String(32)),
        sa.Column("media_group_id", sa.String(64)),
        sa.Column("forward_from_chat_id", sa.BigInteger()),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.UniqueConstraint("channel_id", "message_id", name="uq_channel_post"),
    )
    op.create_index("ix_channel_posts_channel_id", "channel_posts", ["channel_id"])
    op.create_index("ix_channel_posts_posted_at", "channel_posts", ["posted_at"])
    op.create_index("ix_channel_posts_media_group_id", "channel_posts", ["media_group_id"])

    op.create_table(
        "post_reactions",
        sa.Column("post_id", sa.Integer(), sa.ForeignKey("channel_posts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "digest_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic", sa.String(16), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("posted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_digest_runs_user_topic", "digest_runs", ["user_id", "topic"])


def downgrade() -> None:
    op.drop_table("digest_runs")
    op.drop_table("post_reactions")
    op.drop_table("channel_posts")
    op.drop_table("subscriptions")
    op.drop_table("participating_channels")
    op.drop_table("users")
