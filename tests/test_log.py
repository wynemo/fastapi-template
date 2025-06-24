import logging
import os
from unittest import mock

import pytest

from app.core.config import settings
from app.core.log import InterceptHandler, Rotator, add_file_log, get_log_level, setup_logging


# Helper function to clean up environment variables
@pytest.fixture(autouse=True)
def cleanup_env_vars():
    original_environ = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_environ)


# Tests for get_log_level
@pytest.mark.parametrize(
    "env_value, expected_level",
    [
        ("error", logging.ERROR),
        ("warning", logging.WARNING),
        ("debug", logging.DEBUG),
        ("info", logging.INFO),
        ("", logging.INFO),
        ("invalid", logging.INFO),
    ],
)
def test_get_log_level(env_value, expected_level):
    if env_value:
        os.environ["LOG_LEVEL"] = env_value
    elif "LOG_LEVEL" in os.environ:
        del os.environ["LOG_LEVEL"]
    assert get_log_level() == expected_level


def test_get_log_level_no_env():
    if "LOG_LEVEL" in os.environ:
        del os.environ["LOG_LEVEL"]
    assert get_log_level() == logging.INFO


# Tests for InterceptHandler
def test_intercept_handler_emit():
    mock_logger_opt = mock.Mock()
    mock_logger_level = mock.Mock()
    mock_logger_level.name = "INFO"
    mock_logger_opt.log = mock.Mock()

    with (
        mock.patch("app.core.log.logger.opt", return_value=mock_logger_opt),
        mock.patch("app.core.log.logger.level", return_value=mock_logger_level),
    ):
        handler = InterceptHandler()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test_path",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
            func="test_func",
        )
        handler.emit(record)
        mock_logger_opt.log.assert_called_once_with("INFO", "Test message")


def test_intercept_handler_emit_value_error():
    mock_logger_opt = mock.Mock()
    mock_logger_opt.log = mock.Mock()

    with (
        mock.patch("app.core.log.logger.opt", return_value=mock_logger_opt),
        mock.patch("app.core.log.logger.level", side_effect=ValueError),
    ):
        handler = InterceptHandler()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,  # levelno will be used
            pathname="test_path",
            lineno=1,
            msg="Test message with value error",
            args=(),
            exc_info=None,
            func="test_func",
        )
        handler.emit(record)
        mock_logger_opt.log.assert_called_once_with(logging.WARNING, "Test message with value error")


# Tests for setup_logging
@mock.patch("app.core.log.logging.root")
@mock.patch("app.core.log.InterceptHandler")
@mock.patch("app.core.log.LOG_LEVEL", logging.DEBUG)  # Example level
@mock.patch("app.core.log.logging.getLogger")
def test_setup_logging(mock_get_logger, mock_intercept_handler, mock_logging_root):
    # Mock the logger manager's loggerDict
    mock_logger_instance = mock.Mock()
    mock_logger_instance.handlers = [mock.Mock()]  # Simulate existing handlers
    mock_get_logger.return_value = mock_logger_instance

    # Simulate some loggers in loggerDict
    logging.root.manager.loggerDict = {
        "some_logger": mock.Mock(),
        "another_logger": mock.Mock(),
    }

    setup_logging()

    mock_logging_root.setLevel.assert_called_once_with(logging.DEBUG)
    assert len(mock_logging_root.handlers) == 1
    assert isinstance(mock_logging_root.handlers[0], mock.Mock)  # InterceptHandler is mocked

    # Check that specified loggers and those in loggerDict are processed
    expected_loggers_to_process = [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "fastapi",
        "asyncio",
        "starlette",
        "some_logger",
        "another_logger",
    ]

    processed_loggers = set()
    for call_args in mock_get_logger.call_args_list:
        processed_loggers.add(call_args[0][0])

    assert all(name in processed_loggers for name in expected_loggers_to_process)

    # Check that handlers are cleared and propagate is set to True for all processed loggers
    for logger_name in processed_loggers:
        logger_mock = mock_get_logger(logger_name)
        assert logger_mock.handlers == []
        assert logger_mock.propagate is True

    # Clean up loggerDict for other tests
    logging.root.manager.loggerDict = {}


# Tests for Rotator
import datetime


def test_rotator_initialization():
    size = 1024
    rotation_time_str = "14:30"
    rotation_time_obj = datetime.datetime.strptime(rotation_time_str, "%H:%M").time()

    # Mock datetime.now() to control current time
    now = datetime.datetime(2023, 1, 1, 10, 0, 0)  # Before rotation time
    with mock.patch("app.core.log.datetime") as mock_datetime:
        mock_datetime.datetime.now.return_value = now
        mock_datetime.datetime.strptime.side_effect = lambda d, f: datetime.datetime.strptime(d, f)
        mock_datetime.timedelta.side_effect = lambda **kwargs: datetime.timedelta(**kwargs)

        rotator = Rotator(size=size, at=rotation_time_obj)
        assert rotator._size_limit == size
        expected_time_limit = now.replace(hour=rotation_time_obj.hour, minute=rotation_time_obj.minute, second=0)
        assert rotator._time_limit.hour == expected_time_limit.hour
        assert rotator._time_limit.minute == expected_time_limit.minute

    # Test when current time is past rotation time
    now_past_rotation = datetime.datetime(2023, 1, 1, 15, 0, 0)  # After rotation time
    with mock.patch("app.core.log.datetime") as mock_datetime:
        mock_datetime.datetime.now.return_value = now_past_rotation
        mock_datetime.datetime.strptime.side_effect = lambda d, f: datetime.datetime.strptime(d, f)
        mock_datetime.timedelta.side_effect = lambda **kwargs: datetime.timedelta(**kwargs)
        mock_datetime.datetime.side_effect = lambda *args, **kwargs: datetime.datetime(*args, **kwargs)

        rotator_past = Rotator(size=size, at=rotation_time_obj)
        expected_time_limit_past = now_past_rotation.replace(
            hour=rotation_time_obj.hour, minute=rotation_time_obj.minute, second=0
        ) + datetime.timedelta(days=1)
        assert rotator_past._time_limit.day == expected_time_limit_past.day
        assert rotator_past._time_limit.hour == expected_time_limit_past.hour


def test_rotator_should_rotate_size_limit():
    rotator = Rotator(size=100, at=datetime.time(12, 0))
    mock_file = mock.Mock()
    mock_file.tell.return_value = 90
    message_content = "This is a test message"  # len = 22
    mock_message = {
        "record": {"time": mock.Mock(timestamp=lambda: rotator._time_limit.timestamp() - 100)}
    }  # Ensure time is before limit

    assert rotator.should_rotate(message_content, mock_file) is True
    mock_file.seek.assert_called_once_with(0, 2)


def test_rotator_should_rotate_time_limit():
    rotation_time = datetime.time(12, 0)
    # Ensure current time is before rotation time for initial setup
    now = datetime.datetime(2023, 1, 1, 10, 0, 0)
    with mock.patch("app.core.log.datetime") as mock_dt:
        mock_dt.datetime.now.return_value = now
        mock_dt.datetime.strptime.side_effect = lambda d, f: datetime.datetime.strptime(d, f)
        mock_dt.timedelta.side_effect = lambda **kwargs: datetime.timedelta(**kwargs)
        mock_dt.datetime.side_effect = lambda *args, **kwargs: datetime.datetime(*args, **kwargs)

        rotator = Rotator(size=1024, at=rotation_time)

    mock_file = mock.Mock()
    mock_file.tell.return_value = 50  # Size is not an issue

    # Simulate message time past the rotation time
    message_time_after_rotation = rotator._time_limit + datetime.timedelta(seconds=1)
    mock_message_record_time = mock.Mock()
    mock_message_record_time.timestamp = mock.Mock(return_value=message_time_after_rotation.timestamp())

    # Simulate a Loguru Message object structure
    mock_loguru_message = mock.Mock()
    mock_loguru_message.record = {"time": mock_message_record_time}
    mock_loguru_message.__len__ = lambda _: 20  # Simulate a message length for size check, accepts 'self'

    original_time_limit = rotator._time_limit
    assert rotator.should_rotate(mock_loguru_message, mock_file) is True
    # Check if _time_limit was advanced by one day
    assert rotator._time_limit == original_time_limit + datetime.timedelta(days=1)


def test_rotator_should_not_rotate():
    rotation_time = datetime.time(12, 0)
    now = datetime.datetime(2023, 1, 1, 10, 0, 0)
    with mock.patch("app.core.log.datetime") as mock_dt:
        mock_dt.datetime.now.return_value = now
        mock_dt.datetime.strptime.side_effect = lambda d, f: datetime.datetime.strptime(d, f)
        mock_dt.timedelta.side_effect = lambda **kwargs: datetime.timedelta(**kwargs)
        mock_dt.datetime.side_effect = lambda *args, **kwargs: datetime.datetime(*args, **kwargs)

        rotator = Rotator(size=1024, at=rotation_time)

    mock_file = mock.Mock()
    mock_file.tell.return_value = 50

    # Simulate message time before the rotation time
    message_time_before_rotation = rotator._time_limit - datetime.timedelta(seconds=1)
    mock_message_record_time = mock.Mock()
    mock_message_record_time.timestamp = mock.Mock(return_value=message_time_before_rotation.timestamp())

    # Simulate a Loguru Message object structure
    mock_loguru_message = mock.Mock()
    mock_loguru_message.record = {"time": mock_message_record_time}
    mock_loguru_message.__len__ = lambda _: 20  # Simulate a message length for size check, accepts 'self'

    assert rotator.should_rotate(mock_loguru_message, mock_file) is False


# Tests for add_file_log
@mock.patch("app.core.log.logger.add")
@mock.patch("app.core.log.logger.configure")
@mock.patch("app.core.log.Rotator")
@mock.patch("app.core.log.multiprocessing.get_context")
def test_add_file_log_single_process(mock_get_context, mock_rotator_cls, mock_logger_configure, mock_logger_add):
    mock_rotator_instance = mock.Mock()
    mock_rotator_instance.should_rotate = mock.Mock(return_value=False)  # Example return
    mock_rotator_cls.return_value = mock_rotator_instance

    log_path = "test.log"
    add_file_log(log_path, workers=1)

    mock_logger_configure.assert_called_once_with(patcher=None)
    mock_logger_add.assert_called_once()
    args, kwargs = mock_logger_add.call_args
    assert args[0] == log_path
    assert kwargs["enqueue"] is False
    assert kwargs["context"] is None
    assert kwargs["rotation"] == mock_rotator_instance.should_rotate
    # Clean up created file if any (though it's mocked here)
    if os.path.exists(log_path):
        os.remove(log_path)


@mock.patch("app.core.log.logger.add")
@mock.patch("app.core.log.logger.configure")
@mock.patch("app.core.log.Rotator")
@mock.patch("app.core.log.multiprocessing.get_context")
def test_add_file_log_multi_process(mock_get_context, mock_rotator_cls, mock_logger_configure, mock_logger_add):
    mock_rotator_instance = mock.Mock()
    mock_rotator_instance.should_rotate = mock.Mock(return_value=False)
    mock_rotator_cls.return_value = mock_rotator_instance

    mock_spawn_context = mock.Mock()
    mock_get_context.return_value = mock_spawn_context

    log_path = "test_multi.log"
    add_file_log(log_path, workers=2)

    mock_get_context.assert_called_once_with("spawn")
    mock_logger_configure.assert_called_once_with(patcher=None)
    mock_logger_add.assert_called_once()
    args, kwargs = mock_logger_add.call_args
    assert args[0] == log_path
    assert kwargs["enqueue"] is True
    assert kwargs["context"] == mock_spawn_context
    if os.path.exists(log_path):
        os.remove(log_path)


# Example to ensure settings are available for Rotator in add_file_log if not mocked directly
@mock.patch.object(settings, "log_rotation_size", 1024 * 10)
@mock.patch.object(settings, "log_rotation_time", "00:00")
@mock.patch("app.core.log.logger.add")
@mock.patch("app.core.log.logger.configure")
# We don't mock Rotator itself to test its instantiation with settings
def test_add_file_log_with_real_rotator_instantiation(mock_logger_configure, mock_logger_add):
    log_path = "test_real_rotator.log"

    # Mock datetime.now for predictable Rotator behavior
    now = datetime.datetime(2023, 1, 1, 10, 0, 0)  # Before 00:00 of next day
    with mock.patch("app.core.log.datetime") as mock_datetime:
        mock_datetime.datetime.now.return_value = now
        mock_datetime.datetime.strptime.side_effect = lambda d, f: datetime.datetime.strptime(d, f)
        mock_datetime.timedelta.side_effect = lambda **kwargs: datetime.timedelta(**kwargs)
        mock_datetime.time.side_effect = lambda *args, **kwargs: datetime.time(*args, **kwargs)

        add_file_log(log_path, workers=1)

    mock_logger_add.assert_called_once()
    args, kwargs = mock_logger_add.call_args
    # Check that the rotation function passed is from a Rotator instance
    assert callable(kwargs["rotation"])
    assert hasattr(kwargs["rotation"], "__self__")  # Bound method
    assert isinstance(kwargs["rotation"].__self__, Rotator)

    # Verify rotator was initialized with settings
    rotator_instance = kwargs["rotation"].__self__
    assert rotator_instance._size_limit == settings.log_rotation_size

    expected_rotation_time_obj = datetime.datetime.strptime(settings.log_rotation_time, "%H:%M").time()
    expected_time_limit = now.replace(
        hour=expected_rotation_time_obj.hour, minute=expected_rotation_time_obj.minute, second=0
    )
    if now >= expected_time_limit:  # if now is 00:00 or later
        expected_time_limit += datetime.timedelta(days=1)

    assert rotator_instance._time_limit.hour == expected_time_limit.hour
    assert rotator_instance._time_limit.minute == expected_time_limit.minute

    if os.path.exists(log_path):
        os.remove(log_path)
