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
    service_name: str = "payment-service"
    environment: EnvironmentEnum = EnvironmentEnum.DEV


class LoggerSettings(CustomBaseSettings):
    log_level: str = "DEBUG"
    app_logger_name: str = "app_logger"
    api_logger_name: str = "api_logger"


class BrokerSettings(CustomBaseSettings):
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_acks: int = 1  # Wait for leader to acknowledge
    kafka_retries: int = 3
    kafka_enable_idempotence: bool = True


class SqlEngineConfig(BaseModel):
    pool_pre_ping: bool = True
    pool_recycle: int = 3600
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False


class SqlSessionConfig(BaseModel):
    expire_on_commit: bool = False


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
