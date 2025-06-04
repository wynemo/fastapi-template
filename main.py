import argparse
import os
import time

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from starlette.types import Scope
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

# todo add cors middleware


class StaticFilesCache(StaticFiles):
    """
    这个类对html以及txt不缓存，其他文件缓存
    不缓存html，txt的原因是避免nextjs出现404的情况（html与js不一致）
    """

    def __init__(self, *args, cachecontrol="no-cache, no-store, must-revalidate", **kwargs):
        self.cachecontrol = cachecontrol
        super().__init__(*args, **kwargs)

    def file_response(
        self,
        full_path,
        stat_result: os.stat_result,
        scope: Scope,
        status_code: int = 200,
    ) -> Response:
        if full_path.endswith(".html") or full_path.endswith(".txt"):
            resp: Response = FileResponse(full_path, status_code=status_code, stat_result=stat_result)
            resp.headers.setdefault("Cache-Control", self.cachecontrol)
            return resp
        else:
            return super().file_response(full_path, stat_result, scope, status_code)


# # # http://127.0.0.1:8000/index.html 访问前端页面
try:
    front_folder = os.path.join(os.path.dirname(__file__), "frontend/dist")
    os.makedirs(front_folder, exist_ok=True)
    # 挂载静态文件目录, 用于提供前端页面
    app.mount("/", StaticFilesCache(directory=front_folder), name="static")
except Exception as e:
    logger.error(f"静态文件目录挂载失败: {e}")

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
    _format = "{time:YYYY-MM-DD at HH:mm:ss} | {level} | {extra[request_id]} | {message}"
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
