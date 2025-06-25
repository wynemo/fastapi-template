import logging
from unittest import mock

import pytest
from uvicorn import Config as UvicornConfig

from app.core.log import logger  # Assuming setup_logging is not called directly by tests but by MyConfig
from app.core.server_config import MyConfig


# This is the active fixture for resetting logger state:
# This is the active fixture for resetting logger state:
@pytest.fixture(autouse=True)
def reset_logger_state():  # Renamed from _refined
    original_core_obj = logger._core

    # Store a snapshot of the original handlers' IDs and the handlers themselves
    # This is important if the _core object itself is replaced during a test.
    original_handlers_dict_snapshot = original_core_obj.handlers.copy()

    # Store the ID of Loguru's internally managed stderr handler, if any
    original_internal_stderr_id = getattr(logger, "_stderr_handler_id", None)

    yield  # Test runs here

    # --- Cleanup Phase ---

    # 1. Get the logger._core object that was active at the end of the test.
    #    This might be the original one or one assigned by the test (e.g., child process simulation).
    active_core_at_test_end = logger._core

    # 2. Restore the original _core object to Loguru's global logger.
    #    This is the most critical step for resetting the logger's fundamental state.
    logger._core = original_core_obj

    # 3. Ensure the handlers in the now-restored original_core_obj match its pre-test state.
    #    If active_core_at_test_end was original_core_obj, handlers might have been added/removed from it.
    #    If active_core_at_test_end was a *different* object, original_core_obj should be untouched by
    #    direct handler additions to that other core, but we still need to ensure its state is pristine.

    # Get current handlers in the (restored) original_core_obj
    current_handlers_in_original_core = logger._core.handlers  # This is original_core_obj.handlers

    # Remove any handlers that are now in original_core_obj.handlers but weren't in the snapshot
    ids_to_remove = []
    for handler_id in list(current_handlers_in_original_core.keys()):  # Iterate over copy of keys
        if handler_id not in original_handlers_dict_snapshot:
            ids_to_remove.append(handler_id)

    for handler_id in ids_to_remove:
        try:
            # logger.remove() operates on logger._core, which is now original_core_obj
            logger.remove(handler_id)
        except ValueError:  # Handler already removed or ID invalid
            pass

    # Add back any handlers that were in the snapshot but are now missing from original_core_obj.handlers
    # This covers cases where a test might have removed a handler from the original_core_obj.
    # Re-adding requires the full handler configuration, which is complex.
    # A simpler approach for now: if a handler from the snapshot is missing,
    # copy it back directly from the snapshot. This assumes handler objects are reusable.
    for handler_id, handler_obj in original_handlers_dict_snapshot.items():
        if handler_id not in current_handlers_in_original_core:  # Check against the current state after removals
            # Check if the handler_id from snapshot still exists with the same object,
            # if not, or if ID is completely missing, restore it.
            # This handles cases where the handler object itself might have been replaced or removed.
            current_handlers_in_original_core[handler_id] = handler_obj

    # 4. Restore Loguru's internal _stderr_handler_id state.
    if original_internal_stderr_id is not None:
        logger._stderr_handler_id = original_internal_stderr_id
    elif hasattr(logger, "_stderr_handler_id"):
        # If it wasn't there originally but exists now, it was added by the test.
        delattr(logger, "_stderr_handler_id")


def test_myconfig_initialization_core_copying():
    """Test MyConfig.__init__ correctly copies logger._core before super().__init__ potentially modifies logger."""
    pristine_logger_core = logger._core
    pristine_logger_handlers = pristine_logger_core.handlers.copy()

    # Temporarily disable MyConfig.configure_logging to isolate the self.handlers assignment
    with mock.patch.object(MyConfig, "configure_logging", lambda x: None):
        config_for_handlers_check = MyConfig(app=None, log_level="info")

    # MyConfig.__init__ assigns logger._core.handlers directly to self.handlers, it's not a copy.
    # So, config_for_handlers_check.handlers should be the same object as pristine_logger_core.handlers
    # (assuming pristine_logger_core.handlers itself hasn't changed identity between its capture and MyConfig init).
    assert hasattr(config_for_handlers_check, "handlers"), "MyConfig instance should have a 'handlers' attribute"
    assert config_for_handlers_check.handlers is pristine_logger_core.handlers, (
        "config.handlers should be the same object as logger._core.handlers at the time of MyConfig initialization"
    )
    # Ensure logger._core itself was not altered by the MyConfig(app=None) call with configure_logging mocked
    assert logger._core is pristine_logger_core, (
        "Global logger._core object identity should not change if configure_logging is no-op"
    )
    assert logger._core.handlers == pristine_logger_handlers, (
        "Global logger._core.handlers should not change if configure_logging is no-op"
    )


def test_myconfig_initialization_calls_self_configure_logging():
    """Test MyConfig.__init__ calls self.configure_logging (likely via super().__init__ call chain)."""
    with mock.patch.object(MyConfig, "configure_logging") as mock_self_configure_logging:
        MyConfig(app=None, log_level="info")
        mock_self_configure_logging.assert_called_once()


# Fixture to provide a MyConfig instance where configure_logging was NOT run during __init__
@pytest.fixture
def myconfig_instance_no_init_logging():
    original_configure_logging_method = MyConfig.configure_logging
    MyConfig.configure_logging = lambda x: None  # Temporarily make it a no-op for __init__
    try:
        instance = MyConfig(app=None, log_level="info")
    finally:
        MyConfig.configure_logging = original_configure_logging_method  # Restore original method
    return instance


@mock.patch("app.core.server_config.setup_logging")  # Mock the setup_logging function
@mock.patch("app.core.server_config.sys.stderr")  # Mock sys.stderr
def test_myconfig_configure_logging_parent_process_scenario(
    mock_stderr, mock_setup_logging, myconfig_instance_no_init_logging
):
    """
    Test MyConfig.configure_logging in a simulated parent process scenario.
    The 'else' branch of the condition `if not logger._core.handlers is self.core.handlers:` is taken.
    """
    config = myconfig_instance_no_init_logging  # Use the fixture

    # Pre-condition for "else" (parent) path:
    # In MyConfig.__init__ (with configure_logging no-op'd by fixture),
    # config.handlers was assigned from logger._core.handlers.
    # We expect them to be the same object at this point.
    assert hasattr(config, "handlers"), "Config instance should have 'handlers' attribute"
    assert logger._core.handlers is config.handlers, (
        "Pre-condition: logger._core.handlers should be the same object as config.handlers"
    )

    # Store the identity of the handlers dict that MyConfig captured.
    # This is what MyConfig's logic will compare against.
    captured_handlers_in_config = config.handlers
    original_logger_core_identity = logger._core

    # Call the actual configure_logging method on the instance
    with mock.patch.object(logger, "add", return_value=None) as mock_logger_add:
        MyConfig.configure_logging(config)  # Call the real method

    # Assertions for the "else" (parent) path:
    # 1. The condition `logger._core.handlers is config.handlers` should have been true.
    #    The test setup ensures this by making logger._core.handlers and config.handlers the same object.
    #    The `else` block should have been executed.

    # 2. logger.add was called to add the new stderr handler.
    #    This call happens in the `else` block.
    mock_logger_add.assert_called_once_with(mock_stderr, level=logging.INFO)

    # 3. setup_logging was called (also in the `else` block).
    mock_setup_logging.assert_called_once()

    # 4. It's possible that logger.add() replaces logger._core.
    #    We are not asserting the identity of logger._core itself against its pre-call state,
    #    as that's an internal Loguru behavior. The key is that the correct branch of logic was taken.
    #    The fixture `reset_logger_state` will handle restoring the logger.


@mock.patch("app.core.server_config.setup_logging")
@mock.patch("app.core.server_config.sys.stderr")
def test_myconfig_configure_logging_child_process_scenario(
    mock_stderr, mock_setup_logging, myconfig_instance_no_init_logging
):
    """
    Test MyConfig.configure_logging in a simulated child process scenario.
    The 'if' branch of the condition `if not logger._core.handlers is self.core.handlers:` is taken.
    """
    config = myconfig_instance_no_init_logging  # Use the fixture

    # Simulate the child process condition: make global logger._core.handlers a *different object*
    # than config.handlers (which holds the handlers from the time of __init__).
    # This ensures `if logger._core.handlers is not self.handlers:` (from MyConfig's perspective) is TRUE.
    assert hasattr(config, "handlers"), "Config instance should have 'handlers' attribute"
    original_handlers_in_config = config.handlers # This is the dict MyConfig captured.
    logger._core.handlers = {}  # Make global logger's current handlers a new, different dict object.
    assert logger._core.handlers is not original_handlers_in_config, "Simulated condition: logger._core.handlers should differ from config.handlers"


    # Call the actual configure_logging method
    with mock.patch.object(logger, "add", return_value=None) as mock_logger_add:
        MyConfig.configure_logging(config)  # Call the real method

    # Assertions for the "if" (child) path:
    # 1. logger._core.handlers should have been replaced with config.handlers (original_handlers_in_config).
    #    The actual logger._core object might be different if logger.add() replaced it,
    #    but its .handlers attribute should now be the one from config.handlers.
    assert logger._core.handlers is original_handlers_in_config, \
        "In child path, logger._core.handlers should be set to config.handlers"

    # 2. logger.add was called to add the new stderr handler.
    #    This call happens in the `if` block.
    mock_logger_add.assert_called_once_with(mock_stderr, level=logging.INFO)

    # 3. setup_logging was called (also in the `if` block).
    mock_setup_logging.assert_called_once()

    # Note: No need to manually restore logger._core here,
    # the `reset_logger_state` fixture handles logger state restoration.


@mock.patch.object(UvicornConfig, "configure_logging", autospec=True)  # Outermost patch, last mock param
@mock.patch("app.core.server_config.setup_logging")  # Middle patch, middle mock param
@mock.patch("app.core.server_config.sys.stderr")  # Innermost patch, first mock param
def test_myconfig_calls_super_configure_logging(
    mock_stderr_arg,  # Corresponds to @mock.patch("...sys.stderr")
    mock_setup_logging_arg,  # Corresponds to @mock.patch("...setup_logging")
    mock_uvicorn_config_logging_arg,  # Corresponds to @mock.patch.object(UvicornConfig, "configure_logging")
    myconfig_instance_no_init_logging,
):
    """Test that MyConfig.configure_logging calls super().configure_logging()."""
    config = myconfig_instance_no_init_logging  # Use the fixture

    # Call the actual configure_logging method
    with mock.patch.object(logger, "add", return_value=None):
        MyConfig.configure_logging(config)  # Call the real method

    # We are asserting that UvicornConfig.configure_logging (the super call) was called
    mock_uvicorn_config_logging_arg.assert_called_once_with(config)
