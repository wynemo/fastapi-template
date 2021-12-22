# encoding=utf-8
import datetime
import logging
import os
import sys

import loguru

from app.core.config import settings

__all__ = ['logger', 'LOG_LEVEL', 'JSON_LOGS']

logger = loguru.logger
LOG_LEVEL = get_log_level()
JSON_LOGS = True if os.environ.get("JSON_LOGS", "0") == "1" else False

def get_log_level():
    try:
        _key = 'LOG_LEVEL'
        level = os.environ.get(_key)

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
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        logging_name = logging.__file__
        if logging_name.endswith('.pyc'):
            logging_name = logging_name.rstrip('c')
        while logging_name.endswith(frame.f_code.co_filename):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging(log_path):
    # intercept everything at the root logger
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(LOG_LEVEL)

    # remove every other logger's handlers
    # and propagate to root logger
    for name in logging.root.manager.loggerDict.keys():
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True

    # configure loguru
    logger.configure(handlers=[{"sink": sys.stdout, "serialize": JSON_LOGS, "level": LOG_LEVEL}])
    # add new configuration
    add_file_log(log_path)

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

def add_file_log(log_path, _filter=lambda _: True):
    rotator = Rotator(size=settings.log_rotation_size,
                      at=datetime.datetime.strptime(settings.log_rotation_time, "%H:%M"))
    logger.add(
        log_path,  # log file path
        level=LOG_LEVEL,  # logging level
        # format="{time:YYYY-MM-DD at HH:mm:ss} | {level} | {message}", #format of log
        enqueue=True,  # set to true for async or multiprocessing logging
        backtrace=False,  # turn to false if in production to prevent data leaking
        rotation=rotator.should_rotate,  # file size or time to rotate
        retention="10 Days",  # how long a the logging data persists
        compression="zip",  # log rotation compression
        serialize=JSON_LOGS,  # if you want it JSON style, set to true. But also change the format
        filter=_filter,
    )


if __name__ == '__main__':
    foo = 'bar'
    logger.info(f'example {foo} test')

