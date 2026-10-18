"""Command line entry point: ``taskboard-api serve | migrate | create-admin``."""

import argparse
import logging
import os
import sys
from collections.abc import Sequence

from alembic import command
from alembic.config import Config
from pydantic import ValidationError

from taskboard_api.config import Settings
from taskboard_api.logging_config import configure_logging

logger = logging.getLogger("taskboard_api.cli")


def alembic_config(database_url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", "taskboard_api:migrations")
    # ConfigParser interpolation would treat "%" in a password as syntax.
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def _migrate(database_url: str) -> int:
    command.upgrade(alembic_config(database_url), "head")
    logger.info("database migrated to head")
    return 0


def _serve(settings: Settings) -> int:
    import uvicorn

    from taskboard_api.api.app import create_app

    uvicorn.run(
        create_app(settings),
        host=settings.api_host,
        port=settings.api_port,
        log_config=None,
        access_log=False,
        server_header=False,
        proxy_headers=False,
    )
    return 0


def _create_admin(settings: Settings) -> int:
    from taskboard_api.composition import Container
    from taskboard_api.domain.commands import RegisterCommand
    from taskboard_api.services.bootstrap import AdminBootstrapService

    try:
        admin = RegisterCommand(
            email=os.environ.get("ADMIN_EMAIL", ""),
            display_name=os.environ.get("ADMIN_DISPLAY_NAME", "Administrator"),
            password=os.environ.get("ADMIN_PASSWORD", ""),
        )
    except ValidationError as exc:
        fields = sorted({str(err["loc"][0]) for err in exc.errors()})
        logger.error(
            "ADMIN_EMAIL / ADMIN_PASSWORD are missing or invalid", extra={"fields": fields}
        )
        return 2
    container = Container(settings)
    try:
        with container.unit_of_work() as uow:
            outcome = AdminBootstrapService(
                uow=uow, hasher=container.hasher, clock=container.clock
            ).ensure_admin(admin)
    finally:
        container.close()
    logger.info("admin account %s", outcome.value, extra={"email": admin.email})
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="taskboard-api")
    parser.add_argument("command", choices=["serve", "migrate", "create-admin"])
    args = parser.parse_args(argv)
    if args.command == "migrate":
        configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
        return _migrate(os.environ["DATABASE_URL"])
    settings = Settings()
    configure_logging(settings.log_level)
    if args.command == "serve":
        return _serve(settings)
    return _create_admin(settings)


if __name__ == "__main__":
    sys.exit(main())
