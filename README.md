# 🎯 Goal Getter Backend

API backend para o sistema **Goal Getter** — gestão de equipes e acompanhamento de atividades diárias (daily stand-up digital) da UFPI.

## Stack

| Tecnologia | Versão |
|---|---|
| Python | 3.13 |
| FastAPI | 0.111+ |
| PostgreSQL | 15+ |
| SQLAlchemy | 2.0+ |
| Docker | Compose v2 |
| Poetry | 1.8+ |

## Pré-requisitos

- **Python 3.13** (recomendamos [pyenv](https://github.com/pyenv/pyenv))
- **Poetry** (`curl -sSL https://install.python-poetry.org | python3 -`)
- **Docker** e **Docker Compose** v2

---

## 🚀 Início Rápido

### Opção 1: Docker Compose (Recomendado)

```bash
# 1. Copiar .env e ajustar DATABASE_URL para usar "db" como host
cp .env.example .env

# 2. Subir backend + PostgreSQL
docker compose up --build -d

# 3. Verificar logs
docker compose logs backend -f

# 4. Acessar Swagger UI
open http://localhost:8881/docs
```

### Opção 2: Desenvolvimento Local (Poetry + Docker DB)

```bash
# 1. Configurar Python 3.13 via pyenv
pyenv install 3.13.9
pyenv local 3.13.9

# 2. Instalar dependências
poetry env use $(pyenv which python)
poetry install

# 3. Copiar .env (ajustar DATABASE_URL para localhost:5472)
cp .env.example .env

# 4. Subir apenas o PostgreSQL
docker compose up db -d

# 5. Executar migrações
poetry run alembic upgrade head

# 6. Iniciar o servidor
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> **VS Code:** Selecione o interpretador em `Cmd + Shift + P` → `Python: Select Interpreter` → `.venv/bin/python`

---

## 🔐 Credenciais Padrão

Na primeira execução (com `DB_RUN_SEED=true`), o sistema cria automaticamente:

| Recurso | Valor |
|---|---|
| Usuário admin | `admin` |
| Senha admin | `admin` |
| Swagger UI | `http://localhost:8881/docs` (Docker) / `http://localhost:8000/docs` (Local) |

> ⚠️ **Altere a senha do admin** imediatamente em ambientes de homologação e produção.

---

## 📡 Endpoints Principais

| Módulo | Rota Base | Endpoints |
|---|---|---|
| **Auth** | `/api/auth` | Login |
| **Usuarios** | `/api/usuarios` | CRUD, atribuições, perfis |
| **Unidades** | `/api/unidades` | CRUD, criar grupos na unidade |
| **Niveis** | `/api/niveis` | CRUD |
| **Grupos** | `/api/grupos` | Listagem, detalhes, desativar |
| **Daily Configs** | `/api/daily/configs` | Config por ID, config por grupo |
| **Daily Items** | `/api/daily/configs` | Items por mês/dia, CRUD, relatório |
| **Agendamentos** | `/api/agendamentos` | CRUD |
| **Petrvs** | `/api/petrvs` | Entregas por CPF |

Documentação interativa completa disponível em **Swagger UI**: `http://localhost:8881/docs` (Docker Compose) ou `http://localhost:8000/docs` (Local via Poetry)

---

## 🐳 Docker — Multi-Ambiente

| Arquivo | Ambiente | Banco | Hot Reload |
|---|---|---|---|
| `docker-compose.yml` | **Desenvolvimento** | Portas 8881 (API) e 5472 (DB) expostas | ✅ Volume mount |
| `docker-compose-hmg.yml` | **Homologação** | Porta interna | ❌ Imagem pura |
| `docker-compose-prod.yml` | **Produção** | Porta interna, restart policy | ❌ Imagem pura |

```bash
# Desenvolvimento
docker compose up --build -d

# Homologação
docker compose -f docker-compose-hmg.yml up --build -d

# Produção
docker compose -f docker-compose-prod.yml up --build -d
```

---

## 🧪 Testes

```bash
# Rodar todos os testes
poetry run pytest -v

# Com cobertura de código
poetry run pytest --cov=app --cov-report=term-missing

# Checagem de tipo estático
poetry run pyrefly check
```

---

## ⚙️ Variáveis de Ambiente

### Core

| Variável | Descrição | Padrão |
|---|---|---|
| `DATABASE_URL` | String de conexão PostgreSQL | `postgresql://goaluser:goalpass@db:5432/goalgetterdb` |
| `SECRET_KEY` | Chave para assinatura JWT | ⚠️ **Obrigatório alterar** |
| `ALGORITHM` | Algoritmo JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Validade do token | `120` |
| `APP_TIMEZONE` | Fuso horário da aplicação | `America/Fortaleza` |
| `DB_RUN_SEED` | Executar seeder na inicialização | `true` |

### Logging

| Variável | Descrição | Padrão |
|---|---|---|
| `BACKEND_LOGS_ENABLED` | Ativa log em arquivo | `true` |
| `BACKEND_LOG_LEVEL` | Nível de log | `INFO` |
| `BACKEND_LOG_DIR` | Diretório dos logs | `logs` |
| `BACKEND_LOG_RETENTION_DAYS` | Retenção (dias) | `7` |

### Integrações (Opcionais)

| Variável | Descrição | Padrão |
|---|---|---|
| `PETRVS_API_URL` | URL da API do Petrvs | `https://petrvshomolog.ufpi.edu.br/transparencia-api` |
| `PETRVS_ENABLED` | Ativa integração Petrvs | `false` |
| `CHAT_WEBHOOK_URL` | URL do webhook de Chat | (vazio) |
| `CHAT_ENABLED` | Ativa notificações de impedimento | `false` |
| `REDMINE_URL` | URL base do Redmine | (vazio) |
| `REDMINE_API_KEY` | Chave API do Redmine | (vazio) |
| `REDMINE_ENABLED` | Ativa envio de notas ao Redmine | `false` |

---

## 📂 Estrutura do Projeto

```
app/
├── main.py               # FastAPI app factory + lifespan
├── seeder.py              # Seed idempotente (níveis + admin)
├── core/                  # Infraestrutura (config, DB, auth, timezone, logging)
├── models/                # 11 modelos SQLAlchemy (UUID PK, soft delete)
├── schemas/               # 11 schemas Pydantic v2 (from_attributes)
├── routers/               # 9 routers FastAPI (auth, CRUD, daily, petrvs)
└── services/              # 9 services (lógica de negócio)
```

---

## 📖 Documentação

| Arquivo | Conteúdo |
|---|---|
| [AGENTS.md](./AGENTS.md) | Regras de negócio, glossário de domínio, fluxos, permissões |
| [AGENTS-BACKEND.md](./AGENTS-BACKEND.md) | Diretrizes técnicas, padrões de código, arquitetura |
| [Swagger UI](http://localhost:8881/docs) | Documentação interativa da API (`http://localhost:8881/docs` via Docker ou `http://localhost:8000/docs` local) |
