from typing import Any, Protocol


class CustomLoggerProto(Protocol):
    def bind(self, *args: Any, **new_values: Any) -> None:
        """Bind additional context variables to the logger."""
        ...

    def unbind(self, *keys: str) -> None:
        """Unbind (remove) previously bound keys from the logger's context."""
        ...

    def debug(self, *args: Any, **kwargs: Any) -> None:
        """Log a DEBUG-level message."""
        ...

    def info(self, *args: Any, **kwargs: Any) -> None:  # noqa: WPS110
        """Log an INFO-level message."""
        ...

    def warning(self, *args: Any, **kwargs: Any) -> None:
        """Log a WARNING-level message."""
        ...

    def error(self, *args: Any, **kwargs: Any) -> None:
        """Log an ERROR-level message."""
        ...

    def critical(self, *args: Any, **kwargs: Any) -> None:
        """Log a CRITICAL-level message."""
        ...

    def exception(self, *args: Any, **kwargs: Any) -> None:
        """Log an exception with traceback information."""
        ...
