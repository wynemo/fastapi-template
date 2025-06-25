from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    debug: bool = False
    enable_cors: bool = False
    log_rotation_size: int = 10_000_000
    log_rotation_time: str = "00:00"


settings = Settings()
