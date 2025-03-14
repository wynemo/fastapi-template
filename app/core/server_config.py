import copy
import logging
import sys

from uvicorn import Config

from app.core.log import setup_logging, logger

class MyConfig(Config):
    """
    自定义配置类,继承自uvicorn的Config类
    uvicorn 用的spawn，需要通过config把logger._core 传递到子进程里
    """

    def __init__(self, *args, **kwargs):
        """
        初始化方法
        保存logger的core对象,并调用父类初始化
        """
        # 这里core.handlers 里只有文件的handler
        self.core = copy.copy(logger._core)  # _core 是可以序列化的，可以用多进程spawn方式传递
        super().__init__(*args, **kwargs)

    def configure_logging(self) -> None:
        """
        配置日志
        重写父类的configure_logging方法
        确保子进程logger使用父进程传递过来的core对象
        设置日志配置
        """

        super().configure_logging()
        if not logger._core.handlers is self.core.handlers:
            # 父进程里 不会进入这里
            # 子进程里 会进入这里， 使用父进程传递进来的core对象
            logger._core = self.core

            logger.add(sys.stderr, level=logging.INFO)

            setup_logging()
        else:
            # 添加一个handler后
            # 这里loguru logger._core.handlers 会浅拷贝，生成一个新的对象
            # self.core.handlers 还是引用的原有的对像
            # 而原有的对象里只有文件的handler, 这样才能传递到子进程里 (可序列化)
            logger.add(sys.stderr, level=logging.INFO)

            setup_logging()
