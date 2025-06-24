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

    # Temporarily disable MyConfig.configure_logging to isolate the self.core assignment
    with mock.patch.object(MyConfig, "configure_logging", lambda x: None):
        config_for_core_check = MyConfig(app=None, log_level="info")

    assert config_for_core_check.core is not pristine_logger_core, "config.core should be a new object (a copy)"
    assert config_for_core_check.core.handlers == pristine_logger_handlers, (
        "config.core.handlers should be a copy of the handlers from logger._core at the moment of copy"
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
    # After MyConfig's __init__ (with configure_logging no-op'd by fixture),
    # config.core.handlers should be the same dict object as logger._core.handlers.
    # This is because self.core = copy.copy(logger._core) makes self.core.handlers
    # refer to the same dict as logger._core.handlers.
    assert logger._core.handlers is config.core.handlers, (
        "Pre-condition: logger._core.handlers should be the same object as config.core.handlers"
    )

    core_identity_before_method_call = logger._core
    copied_core_in_config = config.core  # This is the core object copied in __init__

    # Call the actual configure_logging method on the instance
    with mock.patch.object(logger, "add") as mock_logger_add:
        MyConfig.configure_logging(config)  # Call the real method

    # Assertions for the "else" (parent) path:
    # 1. logger._core should NOT have been replaced by the config.core that was created in __init__.
    #    The global logger._core object's identity might change due to logger.add internal behavior,
    #    but it should not become the 'copied_core_in_config'.
    assert logger._core is not copied_core_in_config

    # 2. logger.add was called to add the new stderr handler to the global logger
    mock_logger_add.assert_called_once_with(mock_stderr, level=logging.INFO)

    # 3. setup_logging was called
    mock_setup_logging.assert_called_once()


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
    # than config.core.handlers (which holds the handlers from the time of __init__).
    # This ensures `if not logger._core.handlers is self.core.handlers` is TRUE.

    original_global_logger_core_obj_for_restore = logger._core  # To restore at the end
    # Ensure that config.core.handlers is different from what logger._core.handlers will be when the method is called.
    # The fixture `myconfig_instance_no_init_logging` ensures config.core.handlers reflects the state *before* any configure_logging.
    # Now, change the global logger's handlers dict so it's different from config.core.handlers.
    logger._core.handlers = {}  # Make global logger's handlers a new, different dict object.

    expected_logger_core_after_method = config.core  # logger._core should become config.core

    # Call the actual configure_logging method
    with mock.patch.object(logger, "add") as mock_logger_add:
        MyConfig.configure_logging(config)  # Call the real method

    # Assertions for the "if" (child) path:
    # 1. Global logger._core should have been replaced with config.core
    assert logger._core is expected_logger_core_after_method

    # 2. logger.add was called to add the new stderr handler (this time to config.core, which is now logger._core)
    mock_logger_add.assert_called_once_with(mock_stderr, level=logging.INFO)

    # 3. setup_logging was called
    mock_setup_logging.assert_called_once()

    # Restore the original global logger core object to prevent side effects.
    # The fixture also does this, but being explicit can help if fixture has issues.
    logger._core = original_global_logger_core_obj_for_restore


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
    MyConfig.configure_logging(config)  # Call the real method

    # We are asserting that UvicornConfig.configure_logging (the super call) was called
    mock_uvicorn_config_logging_arg.assert_called_once_with(config)
