# FastAPI Template

一个基于FastAPI框架的项目模板

## 主要特性

- **FastAPI框架**: 使用现代化的Python FastAPI框架，提供高性能的API服务
- **消息队列支持**: 集成Kombu消息队列，支持Redis作为消息代理
- **日志系统**:
  - 使用Loguru进行日志管理
  - 支持日志轮转
  - 支持多进程日志处理 (uvicorn 多 worker 模式下, 文件日志由主进程管理)

<details>
<summary>实现多进程日志支持的技术细节</summary>

😀不过多进程还是需要好多hack啊

uvicorn又是用的spawn

😅不过好像也没多大卵用，毕竟gunicorn已经有这些了~

算是又学习了下 spawn模式，python传递变量到子进程，序列化、反序列化

看了下uvicorn、loguru的代码
</details>

- **中间件支持**: 包含请求上下文日志中间件
- **多进程支持**: 支持多worker部署模式
- **Docker支持**: 提供Dockerfile和docker-compose配置

## 项目结构

```
.
├── app/
│   ├── core/           # 核心功能模块
│   ├── schemas/        # Pydantic模型
│   └── config.py       # 应用配置
├── docker-compose.yml  # Docker编排配置
├── Dockerfile         # Docker构建文件
├── requirements.txt   # 生产环境依赖
└── requirements.dev.txt # 开发环境依赖
```

## 快速开始
linux、macos 都是能跑的，windows也能跑

1. 安装uv: https://docs.astral.sh/uv/getting-started/installation/#installation-methods

2. 开发模式运行:
```bash
uv run main.py
```

3. 生产模式运行(多worker):
```bash
uv run main.py --workers 2 --port 8000
```
注：现在uvicorn worker死掉以后 还可以拉起来 不需要用gunicorn了 可以看 https://github.com/encode/uvicorn/issues/517

4. docker compose 运行:
```bash
rm -rf .venv
docker compose up
```
