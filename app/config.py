from pydantic import BaseSettings

class Settings(BaseSettings):
    debug: bool = False
    enable_cors: bool = False

