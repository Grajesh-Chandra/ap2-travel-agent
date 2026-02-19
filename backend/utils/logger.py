"""
Structured JSON Logging with Rotation
For AP2 Travel Agent Demo
"""

import logging
import json
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional

# Ensure logs directory exists
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


# ANSI color codes for console output
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured logging."""

    def __init__(self, agent_name: str):
        super().__init__()
        self.agent_name = agent_name

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "agent": self.agent_name,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields - they are added as attributes directly to the record
        # Standard logging record attributes to skip
        skip_attrs = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "message",
            "asctime",
            "extra",
        }

        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in skip_attrs:
                extra_fields[key] = value

        if extra_fields:
            log_entry["extra"] = extra_fields

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class ColoredConsoleFormatter(logging.Formatter):
    """Colored console output for readability."""

    LEVEL_COLORS = {
        "DEBUG": Colors.GRAY,
        "INFO": Colors.GREEN,
        "WARNING": Colors.YELLOW,
        "ERROR": Colors.RED,
        "CRITICAL": Colors.RED,
    }

    def __init__(self, agent_name: str):
        super().__init__()
        self.agent_name = agent_name

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelname, Colors.RESET)
        timestamp = datetime.utcnow().strftime("%H:%M:%S")

        formatted = (
            f"{Colors.GRAY}{timestamp}{Colors.RESET} "
            f"{color}[{record.levelname:7}]{Colors.RESET} "
            f"{Colors.CYAN}[{self.agent_name}]{Colors.RESET} "
            f"{record.getMessage()}"
        )

        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"

        return formatted


def get_logger(agent_name: str, log_level: str = "DEBUG") -> logging.Logger:
    """
    Create a configured logger for an agent with both file and console handlers.

    Args:
        agent_name: Name of the agent (used in log file name and entries)
        log_level: Minimum log level to capture

    Returns:
        Configured logger instance
    """
    # Sanitize agent name for file
    safe_name = agent_name.lower().replace(" ", "_").replace("-", "_")
    log_file = LOG_DIR / f"{safe_name}.log"

    # Create or get logger
    logger = logging.getLogger(agent_name)

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()

    # Set level
    logger.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))

    # File handler with rotation (10MB, keep 5 backups)
    file_handler = RotatingFileHandler(
        str(log_file),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(JSONFormatter(agent_name))
    logger.addHandler(file_handler)

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColoredConsoleFormatter(agent_name))
    logger.addHandler(console_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


class LogContext:
    """Context manager for logging with extra fields."""

    def __init__(self, logger: logging.Logger, **extra):
        self.logger = logger
        self.extra = extra

    def __enter__(self):
        old_factory = logging.getLogRecordFactory()
        extra = self.extra

        def record_factory(*args, **kwargs):
            record = old_factory(*args, **kwargs)
            record.extra = extra
            return record

        self._old_factory = old_factory
        logging.setLogRecordFactory(record_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self._old_factory)


def log_a2a_message(
    logger: logging.Logger,
    direction: str,  # "SENT" or "RECEIVED"
    from_agent: str,
    to_agent: str,
    message: Dict[str, Any],
    duration_ms: Optional[float] = None,
):
    """Log an A2A protocol message."""
    arrow = "→" if direction == "SENT" else "←"
    logger.info(
        f"A2A {direction}: {from_agent} {arrow} {to_agent}",
        extra={
            "type": "a2a_message",
            "direction": direction,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "message_id": message.get("id"),
            "method": message.get("method"),
            "duration_ms": duration_ms,
            "payload_size": len(json.dumps(message)),
        },
    )


def log_mandate_event(
    logger: logging.Logger,
    event: str,  # "CREATED", "SIGNED", "VERIFIED", "EXPIRED"
    mandate_type: str,
    mandate_id: str,
    details: Optional[Dict[str, Any]] = None,
):
    """Log a mandate lifecycle event."""
    logger.info(
        f"Mandate {event}: {mandate_type} [{mandate_id[:16]}...]",
        extra={
            "type": "mandate_event",
            "event": event,
            "mandate_type": mandate_type,
            "mandate_id": mandate_id,
            **(details or {}),
        },
    )


def log_llm_call(
    logger: logging.Logger,
    model: str,
    prompt_preview: str,
    response_preview: str,
    duration_seconds: float,
    tokens_in: Optional[int] = None,
    tokens_out: Optional[int] = None,
):
    """Log an LLM (Ollama) call."""
    logger.info(
        f"LLM Call [{model}] - {duration_seconds:.2f}s",
        extra={
            "type": "llm_call",
            "model": model,
            "prompt_preview": prompt_preview[:200] + "..."
            if len(prompt_preview) > 200
            else prompt_preview,
            "response_preview": response_preview[:200] + "..."
            if len(response_preview) > 200
            else response_preview,
            "duration_seconds": duration_seconds,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        },
    )


def log_payment_event(
    logger: logging.Logger,
    event: str,  # "AUTHORIZED", "DECLINED", "SETTLED", "REFUNDED"
    transaction_id: str,
    amount: float,
    currency: str = "USD",
    details: Optional[Dict[str, Any]] = None,
):
    """Log a payment processing event."""
    logger.info(
        f"Payment {event}: {transaction_id} - ${amount:.2f} {currency}",
        extra={
            "type": "payment_event",
            "event": event,
            "transaction_id": transaction_id,
            "amount": amount,
            "currency": currency,
            **(details or {}),
        },
    )
