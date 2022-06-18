from contextvars import ContextVar
from uuid import uuid4
import time

import uvicorn
from fastapi import Depends, FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.concurrency import run_in_threadpool

from app.core.log import setup_logging, logger

REQUEST_ID_CTX_KEY = 'request_id'
_request_id_ctx_var: ContextVar[str] = ContextVar(REQUEST_ID_CTX_KEY, default=None)
app = FastAPI()

class RequestContextLogMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        request_id = _request_id_ctx_var.set(str(uuid4()))

        logger.info(
            "request received (in middlware)",
            method=request.method,
            path=request.url.path,
            client=request.client and request.client.host,
            ua=request.headers.get("User-Agent"),
        )

        response = await call_next(request)

        logger.info("request finished (in middleware)")
        response.headers['X-Request-ID'] = get_request_id()

        _request_id_ctx_var.reset(request_id)

        return response

def get_request_id() -> str:
    return _request_id_ctx_var.get()

def patch_log(record):
    record["extra"]["request_id"] = get_request_id()

async def dep():
    logger.info("dep start")
    return "foo"

def test_func():
    logger.info('in test func')
    time.sleep(3)
    

@app.get("/")
async def root(value: str = Depends(dep)):
    logger.info('message from root hanlder')
    await run_in_threadpool(test_func)
    return {"message": value}

@app.get("/foo")
async def foo():
    logger.info('message from foo hanlder')
    return {"message": "Hello World"}

if __name__ == "__main__":
    app.add_middleware(RequestContextLogMiddleware)
    setup_logging('/tmp/logs/app.log', patch_log, _format="{time:YYYY-MM-DD at HH:mm:ss} | {level} | {extra[request_id]} | {message}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
