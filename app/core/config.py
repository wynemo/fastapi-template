from pydantic import BaseSettings

class Settings(BaseSettings):
    debug: bool = False
    enable_cors: bool = False
    log_rotation_size = 10_000_000
    log_rotation_time = '00:00'
