# 🛡️ Diretrizes Técnicas de Backend — RSC-TAE UFPI

> [!NOTE]
> Este arquivo é **auto-suficiente** — contém os detalhes de implementação embutidos diretamente,
> sem dependência de referências a arquivos do repositório de origem.
> Regras de negócio da aplicação (fluxos de solicitação, máquina de estados, comportamentos de domínio) estão documentadas no AGENTS.md principal.

---

## 🗂️ Stack e Tecnologias

| Camada | Tecnologia |
|---|---|
| Framework API | FastAPI (Python 3.13) |
| ORM | SQLAlchemy |
| Servidor | Uvicorn |
| Banco de Dados | PostgreSQL 15+ |
| Autenticação | JWT (`python-jose`) + LDAP |
| Checagem estática | Pyrefly |
| Testes | Pytest |

---

## 🔑 1. Hashing de Senhas (Bcrypt — Sem Passlib)

> [!WARNING]
> O FastAPI tradicionalmente usa `passlib[bcrypt]`, mas versões modernas da biblioteca `bcrypt` causam incompatibilidade de tipos que lança exceções na inicialização. **Não use `passlib`.**

Use a biblioteca `bcrypt` diretamente, conforme as funções canônicas:

```python
import bcrypt

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False
```

---

## 🔒 2. Autenticação JWT

- Tokens expiram em **120 minutos** por padrão (configurável via `ACCESS_TOKEN_EXPIRE_MINUTES` no `.env`).
- Algoritmo: `HS256` (configurável via `ALGORITHM` no `.env`).
- Valide sempre no header `Authorization: Bearer <token>`.
- **Nunca** hardcode o `SECRET_KEY` — carregue sempre de variável de ambiente.

### Geração de Token
```python
from datetime import datetime, timedelta, timezone
from jose import jwt

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
```

### Dependências de Autenticação (FastAPI)
O projeto usa `OAuth2PasswordBearer` com tokenUrl `"api/admin/login"`:

```python
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/admin/login")
```

Duas dependências injetáveis:
- `get_current_admin(token)` — decodifica JWT, valida `role == "admin"` e verifica `usuario.ativo`.
- `get_current_servidor(token)` — decodifica JWT, valida `role == "servidor"` e verifica `servidor.ativo`.

Ambas levantam `HTTP 401` para token inválido e `HTTP 403` para usuário inativo/não autorizado.

### Controle de Role
```python
class RoleRequired:
    def __init__(self, *allowed_roles: str):
        self.allowed_roles = allowed_roles

    def __call__(self, current_admin: dict = Depends(get_current_admin)) -> dict:
        if current_admin.get("role") not in self.allowed_roles:
            raise HTTPException(status_code=403, detail="Acesso negado.")
        return current_admin
```

> [!IMPORTANT]
> Imports de `SessionLocal` e modelos ORM dentro de `get_current_admin`/`get_current_servidor` devem ser **locais** (dentro da função) para evitar dependência circular com `database.py`.

---

## 🧩 3. Organização de Routers por Domínio

Arquivos em `backend/app/routers/`, divisão estrita por domínio/audiência:

| Arquivo | Prefixo | Audiência |
|---|---|---|
| `modelo.py` | `/api/...` | Usuário comum logado |
| `admin.py` | `/api/admin/...` | Admin autenticado |
| `public.py` | `/api/public/...` | Público (sem autenticação) |
| `shared.py` | — | Funções reutilizadas entre routers |

### Função Centralizada de Download de Arquivo (`shared.py`)
Toda lógica de servir arquivos (comprovantes, memoriais, requerimentos) é centralizada em `criar_resposta_arquivo`. Ao adicionar novos endpoints de download, **não duplique** esta lógica:

```python
import mimetypes
from fastapi import HTTPException, status
from fastapi.responses import Response
from app.services.storage_service import storage_manager

def criar_resposta_arquivo(arquivo) -> Response:
    if not arquivo:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    if not storage_manager.exists(arquivo.file_id):
        raise HTTPException(status_code=404, detail="Arquivo físico não encontrado.")
    try:
        content = storage_manager.read(arquivo.file_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler arquivo: {str(e)}")

    media_type, _ = mimetypes.guess_type(arquivo.filename or "arquivo")
    if not media_type:
        media_type = arquivo.content_type or "application/octet-stream"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{arquivo.filename or "arquivo"}"'},
    )

# Wrappers de compatibilidade para endpoints de memorial e requerimento:
def criar_resposta_arquivo_memorial(memorial) -> Response:
    return criar_resposta_arquivo(memorial.arquivo)

def criar_resposta_arquivo_requerimento(requerimento) -> Response:
    return criar_resposta_arquivo(requerimento.arquivo)
```

---

## 📐 4. Modelagem ORM (SQLAlchemy)

### Colunas Padrão Obrigatórias
Todo modelo ORM **deve** ter as seguintes colunas para controle e rastreabilidade:

| Coluna | Tipo SQLAlchemy | Padrão |
|---|---|---|
| `created_at` | `DateTime` | `default=now_in_app_timezone` |
| `updated_at` | `DateTime` | `nullable=True` |
| `ativo` | `Boolean` | `default=True` |

```python
from sqlalchemy import Column, Boolean, DateTime
from app.core.timezone import now_in_app_timezone

class MeuModelo(Base):
    __tablename__ = "minha_tabela"
    # ...campos de domínio...
    created_at = Column(DateTime, default=now_in_app_timezone, nullable=False)
    updated_at = Column(DateTime, nullable=True)
    ativo      = Column(Boolean, default=True, nullable=False)
```

- `ativo` implementa **exclusão lógica** (soft delete). Nunca delete registros fisicamente sem justificativa explícita.
- `created_at` usa `now_in_app_timezone` — **nunca** `datetime.utcnow()` ou `datetime.now()` sem timezone.

---

## 🕐 5. Timezone Institucional (America/Fortaleza)

- O fuso oficial é `America/Fortaleza`, configurado via `APP_TIMEZONE` no `.env`.
- Usa `zoneinfo.ZoneInfo` (stdlib Python 3.9+), sem dependência de `pytz`.

### Funções canônicas de `timezone.py`

```python
from datetime import datetime, time
from zoneinfo import ZoneInfo
from app.core.config import settings

APP_TIMEZONE = ZoneInfo(settings.APP_TIMEZONE)  # ex: ZoneInfo('America/Fortaleza')

def now_in_app_timezone() -> datetime:
    """Datetime atual no fuso da aplicação (com tzinfo)."""
    return datetime.now(APP_TIMEZONE)

def to_app_timezone(value: datetime | None) -> datetime | None:
    """Converte ou 'localiza' um datetime para o fuso da aplicação."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=APP_TIMEZONE)  # assume fuso local
    return value.astimezone(APP_TIMEZONE)

def to_app_isoformat(value: datetime | None) -> str | None:
    """Serializa datetime como string ISO com offset de Fortaleza."""
    app_value = to_app_timezone(value)
    return app_value.isoformat() if app_value else None

def local_day_bounds(day) -> tuple[datetime, datetime]:
    """Retorna início e fim do dia no fuso da aplicação (para queries de intervalo)."""
    start = datetime.combine(day, time.min, tzinfo=APP_TIMEZONE)
    end   = datetime.combine(day, time.max, tzinfo=APP_TIMEZONE)
    return start, end
```

> [!CAUTION]
> Nunca use `datetime.utcnow()` para campos de negócio ou auditoria. Isso causa dessincronização nas queries de intervalo e na exibição no frontend.

---

## 🔄 6. Seeding Idempotente do Banco de Dados

- Executa **apenas** se `DB_RUN_SEED=true` (ou `True`) no arquivo `.env`.
- Antes de inserir, o seeder verifica existência por chave natural:
  - **Critérios**: busca por `criterio_id`
  - **Níveis**: busca por `level`
  - **Saberes**: busca por `saber_id`
- Os dados do catálogo são lidos de `saberes.json` e `niveis.json` no startup.
- O seeder também cria o usuário administrador padrão se não existir.
- Idempotência garante execução múltipla sem erros de `UNIQUE constraint`.

---

## 💾 7. Armazenamento Seguro de Arquivos

### 7.1 Validação de Arquivos (Magic Bytes)
Toda validação usa a função `validate_uploaded_file(file_content, filename, content_type)`.

**Nunca confie em extensão ou `Content-Type` HTTP.** A validação ocorre em 4 camadas:

1. **Tamanho**: rejeita se `len(content) / (1024*1024) > settings.MAX_FILE_SIZE_MB` → HTTP 400.
2. **Extensão na whitelist**: por padrão apenas `.pdf`. Se `PERMITIR_APENAS_PDF=false` no `.env`, adiciona `.png`, `.jpg`, `.jpeg`.
3. **MIME Type**: se `content_type` informado, deve coincidir com o esperado para a extensão.
4. **Magic Number** (proteção definitiva): verifica a assinatura binária dos primeiros bytes:

| Tipo | Extensões | Assinatura Binária |
|---|---|---|
| PDF | `.pdf` | `b'%PDF'` |
| PNG | `.png` | `b'\x89PNG\r\n\x1a\n'` |
| JPEG | `.jpg`, `.jpeg` | `b'\xff\xd8\xff'` ou `b'\xff\xd8'` |

```python
from app.helpers.file_validator import validate_uploaded_file

content = await file.read()
validate_uploaded_file(content, file.filename, file.content_type)
# levanta HTTPException 400 automaticamente em caso de falha
```

### 7.2 Gravação Atômica no Filesystem Local
Para evitar arquivos corrompidos por falhas de sistema, siga o padrão:
1. Grave em arquivo temporário **no mesmo diretório base** (mesmo filesystem = rename atômico)
2. Chame `flush()` + `os.fsync()` para persistência física garantida
3. Use `os.rename()` para mover para o destino final

```python
import os, tempfile

def write_atomic(dest_path: str, content: bytes):
    dir_path = os.path.dirname(dest_path)
    with tempfile.NamedTemporaryFile(dir=dir_path, delete=False) as tmp:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = tmp.name
    os.chmod(tmp_path, 0o640)      # permissões estritas
    os.rename(tmp_path, dest_path) # rename atômico
```

### 7.3 Prevenção de Path Traversal
Use um resolvedor de caminho seguro antes de qualquer leitura ou exclusão:

```python
import os

def _safe_path(base_dir: str, file_id: str) -> str:
    full_path = os.path.realpath(os.path.join(base_dir, file_id))
    if not full_path.startswith(os.path.realpath(base_dir)):
        raise ValueError(f"Path traversal detectado: {file_id}")
    return full_path
```

### 7.4 Permissões de Arquivo
- Sempre configure `0o640` nos arquivos gravados.
- Remova qualquer bit de execução (`os.chmod(path, 0o640)`).

### 7.5 Failover e Self-Healing
Quando `STORAGE_BACKUP_ENABLED=true` no `.env`:
- **Gravação**: arquivo salvo redundantemente no storage secundário.
- **Leitura**: se o storage primário falhar, busca automaticamente no backup.
- **Self-Healing**: após recuperação do backup, restaura a cópia no storage primário.

---

## ☁️ 8. Integração Min.IO / S3

### Estrutura de Chaves no Bucket
```
solicitacoes/{solicitacao_id}/
├── comprovantes/{uuid}.pdf
├── memoriais/{uuid}.pdf
└── requerimentos/{uuid}.pdf
```

O `subdir` passado a `storage_manager.save()` deve refletir essa hierarquia.

### Configurações de Segurança e Resiliência
- Use `S3_SECURE=true` em produção para forçar TLS.
- `S3Storage._configurar_bucket()` ativa na inicialização:
  - **Versionamento** do bucket (para auditoria de versões).
  - **SSE-S3 (AES256)** — criptografia server-side.
- Para storage de **backup**: instancie com `run_setup=False` para não reconfigurar o bucket.
- **Timeout**: `connect_timeout=10s`, `read_timeout=30s` (via `Config` do boto3).
- **Retry**: `max_attempts=3`, `mode='standard'`.

### Variáveis `.env` relevantes
| Variável | Descrição |
|---|---|
| `S3_SECURE` | Força TLS na conexão (`true`/`false`) |
| `S3_BUCKET_VERSIONING` | Ativa versionamento do bucket |
| `S3_SSE` | Ativa criptografia SSE-S3 |

---

## 📊 9. Logs do Backend

- **Saída Dupla**: logs vão para `stdout` (formato legível humano em dev) **e** para `logs/backend/backend.log` (JSON estruturado de uma linha por evento).
- **Rotação Diária**: `TimedRotatingFileHandler`. Retenção configurável por `BACKEND_LOG_RETENTION_DAYS`.
- **Nunca use `print()`** para debug em código de produção.

```python
import logging
logger = logging.getLogger(__name__)
logger.info("Mensagem informativa")
logger.error("Erro crítico", exc_info=True)
```

> [!CAUTION]
> **Gotcha do Alembic**: `alembic/env.py` originalmente chamava `fileConfig(config.config_file_name)`, que resetava o root logger (substituindo todos os handlers por `WARNING`-only). Isso silenciava os logs de tempo de requisição após a primeira migração (`init_db()`).
>
> **Correção aplicada**: `fileConfig()` foi substituído por configuração manual **exclusiva do logger `alembic`**.
> O `main.py` reaaplica `setup_logging()` após `init_db()` como safety net.
>
> **Nunca** reintroduza `fileConfig()` em `alembic/env.py` sem `disable_existing_loggers=False` e sem reaplicar `setup_logging()` depois.

### Variáveis `.env`
| Variável | Descrição | Padrão |
|---|---|---|
| `BACKEND_LOGS_ENABLED` | Ativa escrita em arquivo | `true` |
| `BACKEND_LOG_LEVEL` | Nível de filtro (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `BACKEND_LOG_DIR` | Diretório raiz dos logs | `logs` |
| `BACKEND_LOG_RETENTION_DAYS` | Dias de retenção histórica | `7` |

---

## 🐳 10. DevOps — Docker Multi-Ambiente

O sistema usa três arquivos de Docker Compose para ambientes distintos:

### Desenvolvimento Local (`docker-compose-dev.yml`)
- **Frontend**: Vite Dev Server na porta `5173`, volume montado `./frontend:/app`, watch polling ativo (`usePolling: true` em `vite.config.js`).
- **Backend**: FastAPI com `--reload` na porta `8000`, volume `./backend:/app`.
- **Banco**: Porta `5432` exposta para debug local.
```bash
docker compose -f docker-compose-dev.yml up -d --build
```

### Homologação/Staging (`docker-compose-hmg.yml`)
- **Frontend**: Build de produção servido via **Nginx** na porta `80`.
- **Sem volumes**: Imagem pura, sem montagem de código do host.
```bash
docker compose -f docker-compose-hmg.yml up -d --build
```

### Produção (`docker-compose-prod.yml`)
- **Banco Protegido**: Porta `5432` **não exposta** externamente. Comunicação apenas pela rede privada Docker.
- **Segredos**: Credenciais e chaves JWT carregadas estritamente de variáveis de ambiente.
- **Resiliência**: `restart: unless-stopped` em todos os serviços.
```bash
docker compose -f docker-compose-prod.yml up -d --build
```

---

## 🔧 11. Comandos de Validação

```bash
# Testes automatizados (unitários e integração)
poetry -C backend run pytest -v

# Testes com cobertura de código
poetry -C backend run pytest --cov=app --cov-report=term-missing

# Checagem de tipo estático (Pyrefly)
poetry -C backend run pyrefly check

# Teste específico do subsistema de armazenamento
poetry -C backend run pytest backend/tests/test_storage.py -v

# Auditoria de arquivos órfãos (relatório sem deletar)
poetry -C backend run python cleanup_files.py

# Limpeza física de arquivos órfãos
poetry -C backend run python cleanup_files.py --delete
```

> [!IMPORTANT]
> Toda alteração no backend deve passar por `pytest -v` antes de ser considerada concluída. Nenhum teste pode acessar servidores externos reais — use mocks.
