from enum import StrEnum
from pathlib import Path
from typing import TypeAlias

from fastapi import Depends
from pydantic import Field, SecretStr, BaseModel

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.sql.annotation import Annotated

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


class EnvironmentEnum(StrEnum):
    DEV = "dev"
    STAGE = "stage"
    PROD = "prod"


class CustomBaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class GeneralSettings(CustomBaseSettings):
    service_version: str = "0.0.1"
    service_name: str = "analytics-service"
    environment: EnvironmentEnum = EnvironmentEnum.DEV


class LoggerSettings(CustomBaseSettings):
    log_level: str = "DEBUG"
    app_logger_name: str = "analytics_app_logger"
    api_logger_name: str = "analytics_api_logger"


class BrokerSettings(CustomBaseSettings):
    kafka_bootstrap_servers: str = "payment-kafka:9092"
    kafka_acks: int = 1  # Wait for leader to acknowledge
    kafka_retries: int = 3
    kafka_enable_idempotence: bool = True
    kafka_topic_payment_events: str = "payment-events"
    kafka_consumer_group: str = "analytics-service-group"
    kafka_consumer_max_poll_interval_ms: int = (
        300000  # max time between polls before consumer is considered dead
    )

    kafka_consumer_batch_max_records: int = 10  # max messages per getmany() call
    kafka_consumer_batch_timeout_ms: int = 1000  # getmany() timeout in milliseconds

    outbox_relay_poll_interval: float = 2.0  # seconds between outbox polls
    outbox_relay_batch_size: int = 100  # max events per poll cycle


class SqlEngineConfig(BaseModel):
    pool_pre_ping: bool = True
    pool_recycle: int = 3600
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False


class SqlSessionConfig(BaseModel):
    expire_on_commit: bool = False


class RedisSettings(CustomBaseSettings):
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    TTL: int = 60  # Time-to-live for cached analytics results in seconds
    socket_timeout: float = 0.5
    socket_connect_timeout: float = 0.5

    @property
    def redis_url(self) -> str:
        """
        Constructs the Redis connection URL.

        Returns:
            str: A fully formatted Redis URL string
        """
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


class DatabaseSettings(CustomBaseSettings):
    postgres_user: str = "postgres"
    postgres_password: SecretStr = SecretStr("postgres")
    postgres_host: str = "localhost"
    postgres_port: str = "5432"
    postgres_db: str = "postgres"

    engine: SqlEngineConfig = Field(default_factory=SqlEngineConfig)
    session: SqlSessionConfig = Field(default_factory=SqlSessionConfig)

    @property
    def db_url(self) -> str:
        """
        Constructs the full database connection URL for SQLAlchemy with the asyncpg driver.

        Returns:
            str: A fully formatted database URL string
        """
        db_params = {
            "user": self.postgres_user,
            "password": self.postgres_password.get_secret_value(),
            "host": self.postgres_host,
            "port": self.postgres_port,
            "db": self.postgres_db,
        }
        return "postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}".format(
            **db_params
        )


class Configs(BaseSettings):
    general: GeneralSettings = Field(default_factory=GeneralSettings)
    logger: LoggerSettings = Field(default_factory=LoggerSettings)
    broker: BrokerSettings = Field(default_factory=BrokerSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)


def create_configs() -> Configs:
    """
    Creates and returns a Configs instance.

    This function creates an instance of the `Configs` class, which aggregates
    all configuration settings required by the application

    Returns:
        Configs: The configuration settings.
    """
    return Configs()


ConfigDepends: TypeAlias = Annotated[Configs, Depends(create_configs)]  # type: ignore

app_config: Configs = create_configs()
