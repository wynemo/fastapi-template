import argparse
import time

from fastapi import Depends, FastAPI
from starlette.concurrency import run_in_threadpool
from uvicorn import Server
from uvicorn.supervisors import Multiprocess

from app.core.log import add_file_log, logger
from app.core.middleware import RequestContextLogMiddleware, patch_log
from app.core.server_config import MyConfig

app = FastAPI()


async def dep():
    logger.info("dep start")
    return "foo"


def test_func():
    logger.info("in test func")
    time.sleep(3)


@app.get("/")
async def root(value: str = Depends(dep)):
    logger.info("message from root hanlder")
    await run_in_threadpool(test_func)
    return {"message": value}


@app.get("/foo")
async def foo():
    logger.info("message from foo hanlder")
    return {"message": "Hello World"}


app.add_middleware(RequestContextLogMiddleware)

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
    logger.remove()
    # # 添加文件 sink
    _format = (
        "{time:YYYY-MM-DD at HH:mm:ss} | {level} | {extra[request_id]} | {message}"
    )
    # 文件日志，由父进程处理，避免多个进程同时写入文件导致的文件损坏
    add_file_log("logs/app.log", _format=_format, patcher=patch_log, workers=workers)

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
