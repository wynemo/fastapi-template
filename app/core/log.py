# encoding=utf-8
import logging
import os
import sys

import loguru

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
    logger.add(
        log_path, #log file path
        level=LOG_LEVEL, #logging level
        # format="{time:YYYY-MM-DD at HH:mm:ss} | {level} | {message}", #format of log
        enqueue=True, # set to true for async or multiprocessing logging
        backtrace=False, # turn to false if in production to prevent data leaking
        rotation="10 MB", #file size to rotate
        retention="10 Days", # how long a the logging data persists
        compression="zip", # log rotation compression
        serialize=JSON_LOGS, # if you want it JSON style, set to true. But also change the format
    )

if __name__ == '__main__':
    foo = 'bar'
    logger.info(f'example {foo} test')

