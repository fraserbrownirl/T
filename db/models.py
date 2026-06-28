from datetime import datetime
from enum import Enum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SetupState(str, Enum):
    AWAITING_SUPERGROUP = "awaiting_supergroup"
    ACTIVE = "active"
    PAUSED = "paused"


class ChannelStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    REVOKED = "revoked"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    setup_state: Mapped[str] = mapped_column(String(32), default=SetupState.AWAITING_SUPERGROUP.value)
    feed_supergroup_id: Mapped[int | None] = mapped_column(BigInteger)
    topic_newest_id: Mapped[int | None] = mapped_column(Integer)
    topic_popular_id: Mapped[int | None] = mapped_column(Integer)
    topic_foryou_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="user")


class ParticipatingChannel(Base):
    __tablename__ = "participating_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(512))
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default=ChannelStatus.ACTIVE.value, index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="channel")
    posts: Mapped[list["ChannelPost"]] = relationship(back_populates="channel")


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "channel_id", name="uq_subscription_user_channel"),
        Index("ix_subscriptions_channel_id", "channel_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("participating_channels.id", ondelete="CASCADE"))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    paused: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="subscriptions")
    channel: Mapped["ParticipatingChannel"] = relationship(back_populates="subscriptions")


class ChannelPost(Base):
    __tablename__ = "channel_posts"
    __table_args__ = (
        UniqueConstraint("channel_id", "message_id", name="uq_channel_post"),
        Index("ix_channel_posts_posted_at", "posted_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("participating_channels.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[int] = mapped_column(Integer)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    text_preview: Mapped[str | None] = mapped_column(Text)
    media_type: Mapped[str | None] = mapped_column(String(32))
    media_group_id: Mapped[str | None] = mapped_column(String(64), index=True)
    forward_from_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    channel: Mapped["ParticipatingChannel"] = relationship(back_populates="posts")
    reactions: Mapped["PostReaction | None"] = relationship(back_populates="post", uselist=False)


class PostReaction(Base):
    __tablename__ = "post_reactions"

    post_id: Mapped[int] = mapped_column(ForeignKey("channel_posts.id", ondelete="CASCADE"), primary_key=True)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    post: Mapped["ChannelPost"] = relationship(back_populates="reactions")


class DigestRun(Base):
    __tablename__ = "digest_runs"
    __table_args__ = (Index("ix_digest_runs_user_topic", "user_id", "topic"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    topic: Mapped[str] = mapped_column(String(16))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    posted_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
