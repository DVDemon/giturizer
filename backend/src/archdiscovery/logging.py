import logging

from archdiscovery.config import settings


def configure_logging() -> None:
    """Единая настройка логирования для API и воркеров."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
