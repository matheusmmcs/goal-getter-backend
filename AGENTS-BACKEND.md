# 🛡️ AGENTS-BACKEND.md — Diretrizes Técnicas de Backend

> [!NOTE]
> Este arquivo contém as **diretrizes técnicas de implementação** do Goal Getter Backend.
> Para regras de negócio, fluxos de domínio e glossário, consulte o [AGENTS.md](./AGENTS.md).

---

## 🗂️ Stack e Tecnologias

| Camada | Tecnologia | Versão |
|---|---|---|
| Framework API | FastAPI | 0.111+ |
| Linguagem | Python | 3.13 |
| ORM | SQLAlchemy | 2.0+ |
| Servidor | Uvicorn | 0.30+ |
| Banco de Dados | PostgreSQL | 15+ |
| Autenticação | JWT (`python-jose`) | HS256 |
| Hashing | `bcrypt` (direto, sem passlib) | 4.1+ |
| Configuração | `pydantic-settings` | 2.2+ |
| Migrações | Alembic | 1.13+ |
| HTTP Client | `httpx` | 0.27+ (integrações externas) |
| Gerenciador | Poetry | 1.8+ |
| Checagem estática | Pyrefly | — |
| Testes | Pytest | 8.2+ |

---

## 📁 Estrutura do Projeto

```
goal-getter-backend/
├── AGENTS.md                   # Regras de negócio
├── AGENTS-BACKEND.md           # Este arquivo (diretrizes técnicas)
├── README.md                   # Guia de setup e execução
├── pyproject.toml              # Dependências (Poetry)
├── Dockerfile                  # Multi-stage build
├── docker-compose.yml          # Dev (hot reload + PostgreSQL)
├── docker-compose-hmg.yml      # Homologação
├── docker-compose-prod.yml     # Produção
├── alembic.ini
├── alembic/
│   ├── env.py                  # Importa Base + todos os models
│   ├── script.py.mako
│   └── versions/
├── .env.example
└── app/
    ├── main.py                 # FastAPI factory + lifespan + CORS
    ├── seeder.py               # Seed idempotente
    ├── core/
    │   ├── config.py           # Pydantic BaseSettings
    │   ├── database.py         # Engine + SessionLocal + get_db
    │   ├── security.py         # bcrypt + JWT
    │   ├── timezone.py         # ZoneInfo helpers
    │   ├── logging.py          # Dual output (console + JSON file)
    │   └── dependencies.py     # get_current_user, require_admin
    ├── models/                 # SQLAlchemy ORM (11 modelos)
    │   ├── __init__.py         # Importa todos os modelos
    │   ├── enums.py            # TipoNivelEnum, TipoDiarioItemAnotacaoEnum
    │   ├── usuario.py
    │   ├── unidade.py
    │   ├── nivel.py
    │   ├── grupo.py
    │   ├── atribuicao.py
    │   ├── perfil.py
    │   ├── diario_config.py
    │   ├── diario_item.py
    │   ├── diario_item_anotacao.py
    │   ├── agendamento.py
    │   └── agendamento_historico.py
    ├── schemas/                # Pydantic v2 (11 schemas)
    │   ├── pagination.py       # PaginatedResponse genérico
    │   ├── auth.py
    │   ├── usuario.py
    │   ├── unidade.py
    │   ├── nivel.py
    │   ├── grupo.py
    │   ├── perfil.py
    │   ├── atribuicao.py
    │   ├── daily.py
    │   ├── agendamento.py
    │   └── petrvs.py
    ├── routers/                # FastAPI routers (9 routers)
    │   ├── auth.py
    │   ├── usuarios.py
    │   ├── unidades.py
    │   ├── niveis.py
    │   ├── grupos.py
    │   ├── daily_configs.py
    │   ├── daily_items.py
    │   ├── agendamentos.py
    │   └── petrvs.py
    └── services/               # Lógica de negócio (9 services)
        ├── auth_service.py
        ├── usuario_service.py
        ├── unidade_service.py
        ├── nivel_service.py
        ├── grupo_service.py
        ├── daily_config_service.py
        ├── daily_item_service.py
        ├── agendamento_service.py
        └── petrvs_service.py
```

---

## 🔑 1. Hashing de Senhas (Bcrypt — Sem Passlib)

> [!WARNING]
> **Não use `passlib`.** Versões modernas da biblioteca `bcrypt` causam incompatibilidade de tipos com passlib que lança exceções na inicialização.

Use a biblioteca `bcrypt` diretamente:

```python
import bcrypt

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )
```

Referência: [app/core/security.py](./app/core/security.py)

---

## 🔒 2. Autenticação JWT

- Tokens expiram em **120 minutos** por padrão (`ACCESS_TOKEN_EXPIRE_MINUTES`)
- Algoritmo: `HS256` (`ALGORITHM`)
- Header: `Authorization: Bearer <token>`
- **Nunca** hardcode o `SECRET_KEY` — carregue de `.env`

### Payload do Token
```json
{
  "sub": "uuid-do-usuario",
  "role": "admin" | "user",
  "exp": 1784812431
}
```

### Dependências de Autenticação

```python
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")
```

Duas dependências injetáveis:
- `get_current_user(token, db)` → decodifica JWT, valida `ativo`, `is_autorizado` e `inativo`. Retorna instância `Usuario`
- `require_admin(current_user)` → verifica `is_admin == True`. HTTP 403 se não for admin

Erros:
- `HTTP 401` → token inválido/expirado ou usuário inativo
- `HTTP 403` → usuário não autorizado ou sem permissão de admin

Referência: [app/core/dependencies.py](./app/core/dependencies.py)

---

## 🧩 3. Organização de Routers e Services

### Arquitetura em Camadas

```
Router (recebe request, valida schema, chama service)
  └── Service (lógica de negócio, queries, transações)
       └── Model (ORM SQLAlchemy)
```

### Regras de Organização

| Camada | Responsabilidade | Proibido |
|---|---|---|
| **Router** | Parse de request, validação de schema, envelope de resposta | Queries diretas ao banco |
| **Service** | Lógica de negócio, queries, transações, integrações | Retornar HTTPResponse |
| **Model** | Definição de schema ORM, relationships | Lógica de negócio |

### Padrão de Envelope de Resposta
Todos os routers retornam no formato:
```python
return {"success": True, "message": "Descrição", "data": result}
```

### Paginação
```python
@router.get("/")
def list_items(
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = service.list_all(db, page, size)
    return {"success": True, "message": "...", "data": result}
```

Services de listagem retornam:
```python
{
    "items": [...],
    "count": len(items),       # itens na página atual
    "page": page,              # página (0-indexed)
    "size": size,              # tamanho da página
    "totalPages": ceil(total / size)
}
```

---

## 📐 4. Modelagem ORM (SQLAlchemy)

### Colunas Padrão Obrigatórias

Todo modelo **deve** ter:

| Coluna | Tipo | Padrão | Descrição |
|---|---|---|---|
| `id` | `UUID(as_uuid=True)` | `uuid.uuid4` | Primary key |
| `created_at` | `DateTime` | `now_in_app_timezone` | Data de criação |
| `updated_at` | `DateTime` | `nullable=True` | Última atualização |
| `ativo` | `Boolean` | `True` | Controle de ativação |
| `inativo` | `Boolean` | `False` | Soft delete |

```python
import uuid
from sqlalchemy import Column, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
from app.core.timezone import now_in_app_timezone

class MeuModelo(Base):
    __tablename__ = "minha_tabela"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # ...campos de domínio...
    inativo = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now_in_app_timezone)
    updated_at = Column(DateTime, nullable=True)
    ativo = Column(Boolean, default=True)
```

### Soft Delete
- Desativação via `inativo = True` — **nunca** delete fisicamente
- Listagens **sempre** filtram `inativo == False`
- Entidades relacionadas (ex: atribuições de um grupo) também são desativadas em cascata lógica

### Eager Loading
Use `selectinload` ou `joinedload` para evitar N+1 queries:
```python
from sqlalchemy.orm import selectinload, joinedload

db.query(GrupoTrabalho).options(
    selectinload(GrupoTrabalho.atribuicoes).joinedload(Atribuicao.usuario),
    selectinload(GrupoTrabalho.unidade)
).filter(...)
```

### Proteção contra Vazamento de Senha
O modelo `Usuario` implementa `__iter__` que exclui o campo `senha`:
```python
class Usuario(Base):
    __json_exclude__ = {'senha'}

    def __iter__(self):
        for key in self.__table__.columns.keys():
            if key not in self.__json_exclude__:
                yield key, getattr(self, key)
```

Adicionalmente, os routers de usuarios aplicam `UsuarioResponse.model_validate()` para garantir a exclusão.

---

## 🕐 5. Timezone Institucional (America/Fortaleza)

- Fuso oficial: `America/Fortaleza`, via `APP_TIMEZONE` no `.env`
- Usa `zoneinfo.ZoneInfo` (stdlib Python 3.9+), **sem `pytz`**

### Funções canônicas (`app/core/timezone.py`)

| Função | Uso |
|---|---|
| `now_in_app_timezone()` | Datetime atual com timezone |
| `to_app_timezone(value)` | Converte datetime para o fuso da app |
| `to_app_isoformat(value)` | Serializa como ISO string com offset |
| `local_day_bounds(day)` | Início e fim do dia para queries de intervalo |

> [!CAUTION]
> **Nunca** use `datetime.utcnow()` ou `datetime.now()` sem timezone para campos de negócio ou auditoria.

---

## 🔄 6. Seeding Idempotente

- Executa **apenas** se `DB_RUN_SEED=true` no `.env`
- Verifica existência por chave natural antes de inserir
- Dados seedados:
  - **Níveis**: Chefe de Unidade (101), Gestor de Grupo (201), Participante (202)
  - **Admin**: `usuario='admin'`, `senha=hash('admin')`, `is_admin=True`
- Idempotência garante execução múltipla sem erros de constraint

Referência: [app/seeder.py](./app/seeder.py)

---

## 📊 7. Logs do Backend

- **Saída Dupla**: `stdout` (formato legível) + `logs/app.log` (JSON estruturado)
- **Rotação Diária**: `TimedRotatingFileHandler` com retenção configurável
- **Nunca use `print()`** — sempre `logging.getLogger(__name__)`

```python
import logging
logger = logging.getLogger(__name__)
logger.info("Mensagem informativa")
logger.error("Erro crítico", exc_info=True)
```

> [!CAUTION]
> **Gotcha do Alembic**: `alembic/env.py` **não** deve chamar `fileConfig()` pois isso reseta o root logger.
> O `env.py` deste projeto tem o `fileConfig` comentado. **Nunca** reintroduza sem `disable_existing_loggers=False`.

### Variáveis `.env`
| Variável | Descrição | Padrão |
|---|---|---|
| `BACKEND_LOGS_ENABLED` | Ativa escrita em arquivo | `true` |
| `BACKEND_LOG_LEVEL` | Nível de filtro | `INFO` |
| `BACKEND_LOG_DIR` | Diretório dos logs | `logs` |
| `BACKEND_LOG_RETENTION_DAYS` | Dias de retenção | `7` |

---

## 🐳 8. DevOps — Docker Multi-Ambiente

### Desenvolvimento Local (`docker-compose.yml`)
- **Backend**: FastAPI com `--reload`, porta `8881` exposta no host (`8881:8000`), volume `./app:/app/app` para hot reload
- **Banco**: PostgreSQL 15, porta `5472` exposta no host (`5472:5432`), healthcheck configurado
```bash
docker compose up --build -d
```

### Homologação (`docker-compose-hmg.yml`)
- Sem volumes — imagem pura
- Porta `5432` do banco **não exposta**
```bash
docker compose -f docker-compose-hmg.yml up --build -d
```

### Produção (`docker-compose-prod.yml`)
- Porta do banco **não exposta**
- `restart: unless-stopped` em todos os serviços
- Credenciais via variáveis de ambiente
```bash
docker compose -f docker-compose-prod.yml up --build -d
```

### Dockerfile (Multi-Stage)
```
Stage 1 (builder):
  python:3.13-slim → Poetry → export requirements.txt → pip install to /install

Stage 2 (runtime):
  python:3.13-slim → COPY --from=builder /install → COPY app → CMD uvicorn
```

---

## 🔧 9. Comandos de Validação

```bash
# Rodar em dev com hot reload
docker compose up --build -d

# Logs do backend
docker compose logs backend -f

# Testes automatizados
poetry run pytest -v

# Testes com cobertura
poetry run pytest --cov=app --cov-report=term-missing

# Checagem de tipo estático
poetry run pyrefly check

# Migração Alembic (gerar)
poetry run alembic revision --autogenerate -m "descricao"

# Migração Alembic (aplicar)
poetry run alembic upgrade head
```

> [!IMPORTANT]
> Toda alteração no backend deve passar por `pytest -v` antes de ser considerada concluída.

---

## 🌐 10. Integrações Externas

Todas as integrações são **condicionais** (controladas por flags `*_ENABLED` no `.env`) e executadas em modo **best-effort** (falhas não bloqueiam a operação principal).

| Integração | Flag | Transporte | Uso |
|---|---|---|---|
| **Petrvs** | `PETRVS_ENABLED` | `httpx.AsyncClient` GET | Consulta entregas de PGD por CPF |
| **Redmine** | `REDMINE_ENABLED` | `httpx.Client` PUT | Envia notas para issues |
| **Chat UFPI** | `CHAT_ENABLED` | `httpx.Client` POST | Notifica impedimentos via webhook |

### Variáveis `.env`
| Variável | Descrição |
|---|---|
| `PETRVS_API_URL` | URL base da API Petrvs |
| `PETRVS_ENABLED` | Ativa consulta ao Petrvs |
| `REDMINE_URL` | URL base do Redmine |
| `REDMINE_API_KEY` | Chave API do Redmine |
| `REDMINE_ENABLED` | Ativa envio de notas |
| `CHAT_WEBHOOK_URL` | URL do webhook do Chat |
| `CHAT_ENABLED` | Ativa notificações de impedimento |

---

## ⚠️ Regras Invioláveis

1. **Nunca** use `passlib` — use `bcrypt` diretamente
2. **Nunca** use `print()` — use `logging.getLogger(__name__)`
3. **Nunca** use `datetime.utcnow()` — use `now_in_app_timezone()`
4. **Nunca** hardcode `SECRET_KEY` — carregue de `.env`
5. **Nunca** delete fisicamente — use soft delete (`inativo = True`)
6. **Nunca** retorne o campo `senha` em responses da API
7. **Nunca** reintroduza `fileConfig()` no `alembic/env.py` sem precauções
8. **Nunca** acesse o banco diretamente no router — delegue para o service
