"""Application settings, read from environment variables and validated at startup."""

from typing import Literal, Self

from pydantic import AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class Settings(BaseSettings):
    """All configuration of the API. Missing or invalid values stop the process at startup."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore", frozen=True)

    database_url: SecretStr = Field(description="SQLAlchemy URL, postgresql+psycopg://...")
    database_pool_size: int = Field(default=5, ge=1, le=50)

    redis_url: SecretStr | None = Field(default=None, description="redis:// or rediss:// URL")
    cache_enabled: bool = True
    cache_ttl_seconds: int = Field(default=300, ge=1, le=86_400)
    redis_socket_timeout_seconds: float = Field(default=0.5, gt=0, le=10)
    redis_retry_after_seconds: float = Field(default=30.0, ge=0, le=600)

    service_token: SecretStr = Field(
        description="Shared secret the UI server sends in X-Service-Token"
    )

    session_ttl_hours: int = Field(default=12, ge=1, le=24 * 30)
    password_reset_ttl_minutes: int = Field(default=30, ge=5, le=24 * 60)
    public_ui_url: AnyHttpUrl = Field(description="Base URL of the UI, used in emailed links")
    argon2_time_cost: int = Field(default=3, ge=1, le=10)
    argon2_memory_cost_kib: int = Field(default=65_536, ge=8, le=1_048_576)

    login_rate_limit_per_email: int = Field(default=10, ge=1)
    login_rate_limit_per_ip: int = Field(default=50, ge=1)
    login_rate_window_seconds: int = Field(default=900, ge=1)
    forgot_rate_limit_per_email: int = Field(default=5, ge=1)
    forgot_rate_limit_per_ip: int = Field(default=20, ge=1)
    register_rate_limit_per_ip: int = Field(default=20, ge=1)
    reset_rate_limit_per_ip: int = Field(default=20, ge=1)
    slow_rate_window_seconds: int = Field(default=3600, ge=1)

    storage_backend: Literal["local", "s3"] = "local"
    storage_local_path: str = "/var/lib/taskboard/attachments"
    s3_bucket: str | None = None
    s3_prefix: str = "attachments/"
    s3_kms_key_id: str | None = None
    aws_region: str | None = None
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1)

    webhook_allow_http: bool = False
    webhook_allow_private_targets: bool = False
    webhook_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    webhook_max_attempts: int = Field(default=3, ge=1, le=10)
    webhook_backoff_seconds: float = Field(default=0.5, ge=0, le=10)
    webhook_workers: int = Field(default=4, ge=1, le=32)

    api_host: str = Field(
        default="127.0.0.1", description="Bind address; 0.0.0.0 inside a container"
    )
    api_port: int = Field(default=8000, ge=1, le=65535)

    mailer_log_body: bool = Field(
        default=True, description="Write full email bodies (including reset links) to the log"
    )
    log_level: LogLevel = "INFO"

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        if len(self.service_token.get_secret_value()) < 32:
            msg = "SERVICE_TOKEN must be at least 32 characters"
            raise ValueError(msg)
        if self.storage_backend == "s3" and not self.s3_bucket:
            msg = "S3_BUCKET is required when STORAGE_BACKEND=s3"
            raise ValueError(msg)
        return self

    @property
    def public_ui_base(self) -> str:
        """The UI base URL without a trailing slash."""
        return str(self.public_ui_url).rstrip("/")
