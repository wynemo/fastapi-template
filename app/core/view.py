import inspect
from typing import Any, Callable

from fastapi import Depends
from fastapi.encoders import jsonable_encoder

from app.http_tool import CODE_ERROR, CODE_SUCCESS
from app.schemas.common import CommonResponse


class fastapi_compatible_method:
    """Decorate a method to make it compatible with FastAPI"""

    # It is a descriptor: it wraps a method, and as soon as the method gets associated with a class,
    # it patches the `self` argument with the class dependency and dissolves without leaving a trace.

    def __init__(self, method: Callable):
        self.method = method

    def __set_name__(self, cls: type, method_name: str):
        # Patch the function to become compatible with FastAPI.
        # We only have to declare `self` as a dependency on the class itself: `self = Depends(cls)`.
        patched_method = set_parameter_default(self.method, "self", Depends(cls))
        # Put the method onto the class. This makes our descriptor go completely away
        return setattr(cls, method_name, patched_method)


def set_parameter_default(func: Callable, param: str, default: Any) -> Callable:
    """Set a default value for one function parameter; make all other defaults equal to `...`

    This function is normally used to set a default value for `self` or `cls`:
    weird magic that makes FastAPI treat the argument as a dependency.
    All other arguments become keyword-only, because otherwise, Python won't let this function exist.

    Example:
        set_parameter_default(Cls.method, 'self', Depends(Cls))
    """
    # Get the signature
    sig = inspect.signature(func)
    assert param in sig.parameters  # make sure the parameter even exists

    # Make a new parameter list
    new_parameters = []
    for name, parameter in sig.parameters.items():
        # The `self` parameter
        if name == param:
            # Give it the default value
            parameter = parameter.replace(default=default)
        # Positional parameters
        elif parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
            # Make them keyword-only
            # We have to do it because func(one = default, b, c, d) does not make sense in Python
            parameter = parameter.replace(kind=inspect.Parameter.KEYWORD_ONLY)
        # Other arguments, e.g. variadic: leave them as they are
        new_parameters.append(parameter)

    # Replace the signature
    func.__signature__ = sig.replace(parameters=new_parameters)
    return func


class BaseView(object):
    @classmethod
    def common_response(cls, code, msg, data=None):
        return jsonable_encoder(CommonResponse(code=code, msg=msg, data=data))

    @classmethod
    def success_response(cls, msg, data=None, code=CODE_SUCCESS):
        return cls.common_response(code, msg, data)

    @classmethod
    def error_response(cls, msg, data=None, code=CODE_ERROR):
        return cls.common_response(code, msg, data)
