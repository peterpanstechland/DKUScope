from __future__ import annotations

import logging
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from .config_schema import LoggingConfig
from .paths import get_logs_dir

ROOT_LOGGER = "dkuscope"
MAIN_LOG_NAME = "dkuscope.log"
CRASH_LOG_NAME = "crash.log"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5

_current_config: Optional[LoggingConfig] = None
_handlers_installed = False


def get_logger(category: str) -> logging.Logger:
    return logging.getLogger(f"{ROOT_LOGGER}.{category}")


def get_main_log_path() -> Path:
    return get_logs_dir() / MAIN_LOG_NAME


def get_crash_log_path() -> Path:
    return get_logs_dir() / CRASH_LOG_NAME


def _category_enabled(cfg: LoggingConfig, category: str) -> bool:
    mapping = {
        "app": cfg.log_app,
        "detection": cfg.log_detection,
        "websocket": cfg.log_websocket,
        "calibration": cfg.log_calibration,
        "ota": cfg.log_ota,
        "crash": cfg.log_crash,
    }
    return mapping.get(category, False)


class _CategoryFilter(logging.Filter):
    def __init__(self, cfg: LoggingConfig) -> None:
        super().__init__()
        self._cfg = cfg

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._cfg.enabled:
            return False
        name = record.name
        if not name.startswith(f"{ROOT_LOGGER}."):
            return _category_enabled(self._cfg, "app")
        category = name.split(".", 1)[1]
        return _category_enabled(self._cfg, category)


def _build_formatter() -> logging.Formatter:
    return logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _clear_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def _write_crash(text: str) -> None:
    cfg = _current_config or LoggingConfig()
    if not cfg.enabled or not cfg.log_crash:
        return
    get_logs_dir().mkdir(parents=True, exist_ok=True)
    crash_path = get_crash_log_path()
    with crash_path.open("a", encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")


def _format_exc(exc_type, exc_value, exc_tb) -> str:
    lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    header = f"=== CRASH {threading.current_thread().name} ===\n"
    return header + "".join(lines)


def _install_excepthooks() -> None:
    def handle_exception(exc_type, exc_value, exc_tb) -> None:
        text = _format_exc(exc_type, exc_value, exc_tb)
        _write_crash(text)
        cfg = _current_config or LoggingConfig()
        if cfg.enabled and cfg.log_crash:
            get_logger("crash").error("Uncaught exception:\n%s", text)
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = handle_exception

    if hasattr(threading, "excepthook"):
        def handle_thread_exception(args) -> None:
            text = _format_exc(args.exc_type, args.exc_value, args.exc_traceback)
            _write_crash(text)
            cfg = _current_config or LoggingConfig()
            if cfg.enabled and cfg.log_crash:
                get_logger("crash").error("Thread exception in %s:\n%s", args.thread.name, text)
            threading.__excepthook__(args)

        threading.excepthook = handle_thread_exception


def install_tk_exception_hook(root) -> None:
    default = root.report_callback_exception

    def report_callback_exception(exc_type, exc_value, exc_tb) -> None:
        text = _format_exc(exc_type, exc_value, exc_tb)
        _write_crash(text)
        cfg = _current_config or LoggingConfig()
        if cfg.enabled and cfg.log_crash:
            get_logger("crash").error("Tk callback exception:\n%s", text)
        if default:
            default(exc_type, exc_value, exc_tb)
        else:
            sys.__excepthook__(exc_type, exc_value, exc_tb)

    root.report_callback_exception = report_callback_exception


def configure_logging(cfg: LoggingConfig) -> None:
    global _current_config, _handlers_installed
    _current_config = cfg
    get_logs_dir().mkdir(parents=True, exist_ok=True)

    root = logging.getLogger(ROOT_LOGGER)
    root.setLevel(logging.DEBUG)
    root.propagate = False
    _clear_handlers(root)

    crash_logger = get_logger("crash")
    crash_logger.setLevel(logging.ERROR)
    _clear_handlers(crash_logger)

    if not cfg.enabled:
        root.disabled = True
        if not _handlers_installed:
            _install_excepthooks()
            _handlers_installed = True
        return

    root.disabled = False
    formatter = _build_formatter()

    main_handler = RotatingFileHandler(
        get_main_log_path(),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    main_handler.setFormatter(formatter)
    main_handler.addFilter(_CategoryFilter(cfg))
    main_handler.setLevel(logging.DEBUG)
    root.addHandler(main_handler)

    if cfg.log_crash:
        crash_handler = RotatingFileHandler(
            get_crash_log_path(),
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        crash_handler.setFormatter(formatter)
        crash_handler.setLevel(logging.ERROR)
        crash_logger.addHandler(crash_handler)
        crash_logger.propagate = False

    if not _handlers_installed:
        _install_excepthooks()
        _handlers_installed = True

    get_logger("app").info(
        "Logging configured (app=%s detection=%s websocket=%s calibration=%s ota=%s crash=%s)",
        cfg.log_app, cfg.log_detection, cfg.log_websocket,
        cfg.log_calibration, cfg.log_ota, cfg.log_crash,
    )


def log_event(category: str, level: int, message: str, *args) -> None:
    logger = get_logger(category)
    if _current_config and _current_config.enabled and _category_enabled(_current_config, category):
        logger.log(level, message, *args)
