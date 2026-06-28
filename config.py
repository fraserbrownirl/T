from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str
    telegram_bot_username: str = ""
    database_url: str = "postgresql+asyncpg://telegram_feed:telegram_feed@localhost:5432/telegram_feed"
    database_url_sync: str = "postgresql://telegram_feed:telegram_feed@localhost:5432/telegram_feed"
    redis_url: str = "redis://localhost:6379/0"

    # Fanout pacing
    posts_per_minute_cap: int = 30
    album_buffer_seconds: float = 2.0
    fanout_workers: int = 4

    # Digests
    popular_interval_seconds: int = 4 * 60 * 60
    popular_window_hours: int = 24
    popular_top_k: int = 10
    foryou_interval_seconds: int = 24 * 60 * 60
    foryou_top_k: int = 5

    # Membership reverification
    membership_recheck_interval_seconds: int = 6 * 60 * 60

    # Data retention (Bot Developer Terms 4.2/4.3: store only what is essential).
    # Source post + reaction rows older than this are purged. Must comfortably exceed
    # the longest digest window (popular_window_hours / the For You 24h window) so
    # purging never starves a digest. 0 disables purging.
    post_retention_hours: int = 72
    digest_run_retention_days: int = 30
    retention_interval_seconds: int = 6 * 60 * 60

    # Privacy policy URL surfaced to users (also register this in @BotFather).
    privacy_policy_url: str = ""


settings = Settings()
