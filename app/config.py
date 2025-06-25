from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    debug: bool = False
    enable_cors: bool = False
    openapi_url: str = ""
    json_logs: bool = False


settings = Settings()
