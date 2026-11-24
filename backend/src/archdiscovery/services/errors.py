"""Доменные исключения сервисного слоя."""


class NotFoundError(Exception):
    """Сущность не найдена."""


class DispatchError(Exception):
    """Не удалось поставить задачу в очередь."""
