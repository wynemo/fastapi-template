from contextvars import ContextVar
from uuid import uuid4
import logging
import sys
import time

from fastapi import Depends, FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.concurrency import run_in_threadpool
from uvicorn import Config, Server
from uvicorn.supervisors import Multiprocess

from app.core.log import setup_logging, logger, add_file_log
import argparse

REQUEST_ID_CTX_KEY = 'request_id'
_request_id_ctx_var: ContextVar[str] = ContextVar(REQUEST_ID_CTX_KEY, default=None)
# print('top id is', id(_request_id_ctx_var))
app = FastAPI()

class RequestContextLogMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        request_id = _request_id_ctx_var.set(str(uuid4()))

        logger.info(
            "request received (in middleware)",
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

app.add_middleware(RequestContextLogMiddleware)

class MyConfig(Config):
    """自定义配置类,继承自uvicorn的Config类"""

    def __init__(self, *args, **kwargs):
        """
        初始化方法
        保存logger的core对象,并调用父类初始化
        Args:
            *args: 可变位置参数
            **kwargs: 可变关键字参数
        """
        self.core = logger._core  # _core 是可以序列化的，可以用多进程spawn方式传递
        super().__init__(*args, **kwargs)

    def configure_logging(self) -> None:
        """
        配置日志
        重写父类的configure_logging方法
        确保logger使用相同的core对象
        设置日志配置
        """
        from loguru import logger as _logger

        super().configure_logging()
        if not _logger._core is self.core:
            # 父进程里 不会进入这里
            # 子进程里 会进入这里， 使用父进程传递进来的core对象
            _logger._core = self.core
            _logger.add(sys.stdout, level=logging.INFO)
            setup_logging(need_stream_handler=False)
        else:
            if self.workers > 1:
                # logger 调用了 logger.remove() 没有默认打印东西到控制台的handler，需要stream handler
                # todo stream hanler 看上去像 loguru 的handler， 现在样式不一样
                setup_logging(need_stream_handler=True)
            else:
                setup_logging(need_stream_handler=False)


# 启动 FastAPI 应用
# 使用 uvicorn 启动 FastAPI 应用，监听所有 IP 地址，端口为 8000, worker数量默认为1
# uv run uvicorn main:app 开发模式
# uv run main.py --workers 2 部署模式
if __name__ == "__main__":
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser()
    # 添加workers参数,默认为1个worker
    parser.add_argument("--workers", type=int, default=1, help="Number of workers")
    # 添加port参数,默认端口为8000
    parser.add_argument("--port", type=int, default=8000, help="Port number")
    # 解析命令行参数
    args = parser.parse_args()
    workers = args.workers
    port = args.port

    # 配置日志
    # 重置logger，去掉默认带的sink，否则默认它带的stderr sink无法通过spawn方式传递过去，无法序列化
    # 会报错 TypeError: cannot pickle '_io.TextIOWrapper' object
    if workers > 1:
        logger.remove()
    # # 添加文件 sink
    _format="{time:YYYY-MM-DD at HH:mm:ss} | {level} | {extra[request_id]} | {message}"
    add_file_log("logs/app.log",
        _format=_format,
        patcher=patch_log,
        workers=workers)

    try:
        # 根据workers数量选择启动模式
        if workers < 2:
            # 单进程模式
            config = MyConfig(app, host="0.0.0.0", workers=workers, port=port)
            server = Server(config=config)
            server.run()
        else:
            # 多进程模式
            config = MyConfig("main:app", host="0.0.0.0", workers=workers, port=port)
            server = Server(config=config)
            sock = config.bind_socket()
            Multiprocess(config, target=server.run, sockets=[sock]).run()
    except KeyboardInterrupt:
        pass  # pragma: full coverage
