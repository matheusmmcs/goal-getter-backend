# Goal Getter Backend

Backend service for the Goal Getter app, built with FastAPI, PostgreSQL, and SQLAlchemy.

## Prerequisites
- Python 3.13
- Poetry
- Docker and Docker Compose

## Setup Instructions

### 1. Environment Variables
Copy `.env.example` to `.env` and adjust the variables as needed:
```bash
cp .env.example .env
```

### 2. Configuração do Python e Ambiente Virtual (pyenv + Poetry)

Configure a versão do Python 3.13 via `pyenv` e crie o ambiente virtual local (`.venv`):

```bash
# 1. Instalar e definir a versão do Python no projeto
pyenv install 3.13.9
pyenv local 3.13.9

# 2. Configurar o Poetry para utilizar o Python do pyenv e criar a venv local
poetry env use $(pyenv which python)
poetry install
```

> **Dica (VS Code):** Selecione o interpretador do projeto em `Cmd + Shift + P` -> `Python: Select Interpreter` apontando para `.venv/bin/python`.

### 3. Execução Local

Inicie o banco de dados via Docker:
```bash
docker compose up db -d
```

Run database migrations:
```bash
poetry run alembic upgrade head
```

Run the application:
```bash
poetry run dev
```

### 4. Execução via Docker Compose
To run the full stack (API + DB) via Docker Compose:
```bash
docker compose up -d
```

## Running Tests
```bash
poetry run pytest
```

## Environment Variables
| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | Secret key for JWT signing |
| `ALGORITHM` | JWT algorithm (HS256) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiration time |
| `APP_TIMEZONE` | Timezone for the application |
| `DB_RUN_SEED` | Whether to run seeders on startup |
| `BACKEND_LOGS_ENABLED` | Enable file logging |
| `BACKEND_LOG_LEVEL` | Log level (INFO, DEBUG, etc.) |
| `BACKEND_LOG_DIR` | Directory for log files |
| `BACKEND_LOG_RETENTION_DAYS` | Log retention period |
