"""统一日志 — 替换裸 except:pass + /tmp 路径."""
import logging
import os
from logging.handlers import RotatingFileHandler

_log_dir = os.environ.get('SILENT_LOG_DIR', '/tmp')
_loggers: dict[str, logging.Logger] = {}


def _get_logger(name: str, path: str) -> logging.Logger:
    key = f'{name}:{path}'
    if key in _loggers:
        return _loggers[key]
    logger = logging.getLogger(f'silent.{name}')
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    if not logger.handlers:
        h = RotatingFileHandler(path, maxBytes=1024 * 1024, backupCount=3)
        h.setFormatter(logging.Formatter('%(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
        logger.addHandler(h)
    _loggers[key] = logger
    return logger


def safe_log(name: str, msg: str) -> None:
    """写日志到文件，失败静默（不抛异常）。"""
    try:
        path = os.path.join(_log_dir, f'silent_{name}.log')
        _get_logger(name, path).info(msg)
    except Exception:
        pass
