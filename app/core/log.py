# encoding=utf-8
import datetime
import logging
import multiprocessing
import os
from itertools import chain

import loguru
from app.core.config import settings

__all__ = ["logger", "LOG_LEVEL", "JSON_LOGS"]

logger = loguru.logger


def get_log_level():
    try:
        _key = "LOG_LEVEL"
        level = os.environ.get(_key, "")

        if level.lower() == "error":
            return logging.ERROR
        elif level.lower() == "warning":
            return logging.WARNING
        elif level.lower() == "debug":
            return logging.DEBUG
    except:
        pass
    return logging.INFO


class InterceptHandler(logging.Handler):
    """拦截标准库logging的Handler，将日志转发到loguru"""

    def emit(self, record):
        # 获取对应的loguru日志级别
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            # 如果无法获取对应的level名称,则使用数字级别
            level = record.levelno

        # 获取日志发出的调用位置信息
        frame, depth = logging.currentframe(), 0
        logging_name = logging.__file__
        # 处理.pyc文件的情况
        if logging_name.endswith(".pyc"):
            logging_name = logging_name.rstrip("c")
        # 向上查找调用栈,直到找到最初的调用位置
        while frame.f_back and frame.f_code.co_filename in (logging_name, __file__):
            frame = frame.f_back
            depth += 1

        # 使用loguru记录日志,传入调用深度和异常信息
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


LOG_LEVEL = get_log_level()
JSON_LOGS = True if os.environ.get("JSON_LOGS", "0") == "1" else False


def setup_logging(need_stream_handler=False):
    # 设置根日志记录器的处理器，包括拦截器和流处理器
    # 使用 NTPTimeFormatter 替换原来的 Formatter
    stream_handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    stream_handler.setFormatter(formatter)
    if need_stream_handler:
        logging.root.handlers = [InterceptHandler(), stream_handler]
    else:
        logging.root.handlers = [InterceptHandler()]
    # 设置根日志记录器的日志级别
    logging.root.setLevel(LOG_LEVEL)

    # 移除所有其他日志记录器的处理器
    # 并将日志传播到根日志记录器

    # 需要特殊处理的日志记录器列表
    loggers = (
        "uvicorn",  # uvicorn web服务器主日志
        "uvicorn.access",  # uvicorn访问日志
        "uvicorn.error",  # uvicorn错误日志
        "fastapi",  # FastAPI框架日志
        "asyncio",  # 异步IO日志
        "starlette",  # Starlette框架日志
    )

    # 处理所有日志记录器
    for name in chain(loggers, logging.root.manager.loggerDict.keys()):
        logging_logger = logging.getLogger(name)
        logging_logger.handlers = []  # 清空处理器
        logging_logger.propagate = True  # 启用日志传播


class Rotator:

    def __init__(self, *, size, at):
        now = datetime.datetime.now()

        self._size_limit = size
        self._time_limit = now.replace(hour=at.hour, minute=at.minute, second=at.second)

        if now >= self._time_limit:
            # The current time is already past the target time so it would rotate already.
            # Add one day to prevent an immediate rotation.
            self._time_limit += datetime.timedelta(days=1)

    def should_rotate(self, message, file):
        file.seek(0, 2)
        if file.tell() + len(message) > self._size_limit:
            return True
        if message.record["time"].timestamp() > self._time_limit.timestamp():
            self._time_limit += datetime.timedelta(days=1)
            return True
        return False


def add_file_log(log_path, _format=None, patcher=None, workers=1):
    rotator = Rotator(
        size=settings.log_rotation_size,
        at=datetime.datetime.strptime(settings.log_rotation_time, "%H:%M"),
    )
    if workers > 1:
        spawn_context = multiprocessing.get_context("spawn")
        enqueue = True
    else:
        spawn_context = None
        enqueue = False
    # import sys
    # logger.configure(handlers=[{"sink": sys.stdout, "serialize": JSON_LOGS, "level": LOG_LEVEL, "format": _format}], patcher=patcher)
    logger.configure(patcher=patcher)
    logger.add(
        log_path,  # log file path
        level=LOG_LEVEL,  # logging level
        format=_format,
        # format="{time:YYYY-MM-DD at HH:mm:ss} | {level} | {message}", #format of log
        enqueue=enqueue,  # set to true for async or multiprocessing logging
        backtrace=False,  # turn to false if in production to prevent data leaking
        rotation=rotator.should_rotate,  # file size or time to rotate
        retention="10 Days",  # how long a the logging data persists
        compression="zip",  # log rotation compression
        serialize=JSON_LOGS,  # if you want it JSON style, set to true. But also change the format
        context=spawn_context,
    )


if __name__ == "__main__":
    foo = "bar"
    logger.info(f"example {foo} test")
    logger.opt(exception=True).debug("something bad happened")
