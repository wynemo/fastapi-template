from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request

from app.core.log import logger

REQUEST_ID_CTX_KEY = "request_id"
_request_id_ctx_var: ContextVar[str] = ContextVar(REQUEST_ID_CTX_KEY, default=None)
# print('top id is', id(_request_id_ctx_var))
#


class RequestContextLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        request_id = _request_id_ctx_var.set(str(uuid4()))
        # print('set id is', id(_request_id_ctx_var))

        logger.info(
            "request received (in middleware)",
            method=request.method,
            path=request.url.path,
            client=request.client and request.client.host,
            ua=request.headers.get("User-Agent"),
        )

        response = await call_next(request)

        logger.info("request finished (in middleware)")
        response.headers["X-Request-ID"] = get_request_id()

        _request_id_ctx_var.reset(request_id)

        return response


def get_request_id() -> str:
    # print('get id is', id(_request_id_ctx_var))
    return _request_id_ctx_var.get()


def patch_log(record):
    record["extra"]["request_id"] = get_request_id()
