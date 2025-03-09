# FastAPI Template

一个基于FastAPI框架的项目模板

## 主要特性

- **FastAPI框架**: 使用现代化的Python FastAPI框架，提供高性能的API服务
- **消息队列支持**: 集成Kombu消息队列，支持Redis作为消息代理
- **日志系统**: 
  - 使用Loguru进行日志管理
  - 支持日志轮转
  - 支持多进程日志处理 (uvicorn 多 worker 模式下, 文件日志由主进程管理)
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

1. 安装依赖:
```bash
pip install -r requirements.txt
```

2. 开发模式运行:
```bash
uv run main.py
```

3. 生产模式运行(多worker):
```bash
uv run main.py --workers 2 --port 8000
```
注：现在uvicorn worker死掉以后 还可以拉起来 不需要用gunicorn了 可以看 https://github.com/encode/uvicorn/issues/517
