from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    APP_TIMEZONE: str = 'America/Fortaleza'
    DB_RUN_SEED: bool = True
    BACKEND_LOGS_ENABLED: bool = True
    BACKEND_LOG_LEVEL: str = 'INFO'
    BACKEND_LOG_DIR: str = 'logs'
    BACKEND_LOG_RETENTION_DAYS: int = 7
    CHAT_WEBHOOK_URL: str = ''
    CHAT_ENABLED: bool = False
    REDMINE_URL: str = ''
    REDMINE_API_KEY: str = ''
    REDMINE_ENABLED: bool = False
    PETRVS_API_URL: str = 'https://petrvshomolog.ufpi.edu.br/transparencia-api'
    PETRVS_ENABLED: bool = False

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

settings = Settings()
