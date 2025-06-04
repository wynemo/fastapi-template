# FastAPI Template

一个基于FastAPI框架的项目模板 前端使用nextjs

使用sqlmodel作为orm

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

又重新复习了深拷贝、浅拷贝

确实搭框架，需要对python的基础知识掌握的非常牢固

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

## 前端

frontend目录

后端python代码放外层，把frontend目录放在项目根目录下，这样的层级结构的好处是

打开工程，前端代码也可使用知道后端代码的上下文，这样大模型写前端代码方便，（都不用写文档了😅）

另外python项目放在外层，.venv放在外层，ide才能找到python虚拟环境，放子目录不好（pyproject.toml），感知不到虚拟环境，ide会报错

而对前端代码来说没有这个问题，pnpm一装，ide就能找到，不需要额外配置

所以即使说你是前端项目也是另外一个工程，也推荐把前端代码放在frontend目录

这样既不用开两个ide窗口，又能有足够上下文让大模型写代码方便

框架使用nextjs，tailwind, typesript

不能用antd

前端实现一个首页登录，以及用户管理就行了

https://github.com/vercel/swr
