# 🛡️ AGENTS-BACKEND.md — Diretrizes Técnicas do Backend

> [!NOTE]
> Este arquivo estabelece as **diretrizes técnicas de implementação** para o `goal-getter-backend`.
> Para regras de negócio, glossário de domínio e matriz de permissões, consulte o [AGENTS.md](./AGENTS.md).

---

## 🗂️ Stack Tecnológica

| Camada | Tecnologia | Descrição |
|---|---|---|
| Framework API | FastAPI (0.111+) | Asynchronous Web Framework |
| Runtime | Python 3.13 | Interpretador padrão |
| ORM | SQLAlchemy (2.0+) | Mapeamento relacional com Mapped e mapped_column |
| Migrações | Alembic (1.13+) | Controle de versão de banco de dados |
| Agendador | APScheduler (3.10+) | Motor de execução de cron jobs em background |
| Autenticação | JWT (`python-jose`) + `bcrypt` | Sem uso de `passlib` |
| Fuso Horário | `zoneinfo` (`America/Fortaleza`) | Fuso oficial da aplicação |
| Testes | Pytest (8.2+) | Testes automatizados de API e serviços |

---

## 📁 Arquitetura em 3 Camadas

```
app/
├── routers/        # Recebe request, valida schema Pydantic, chama service
├── services/       # Concentra a lógica de negócio, transações DB e chamadas externas
├── models/         # Definição dos modelos SQLAlchemy e Enums (NivelCodigoEnum, etc.)
├── schemas/        # Schemas Pydantic v2 para validação e serialização
├── core/           # Config, database engine, security (bcrypt), timezone e exceções
├── seeder.py       # Carga idempotente de dados iniciais
└── main.py         # Lifespan factory (Alembic, Seeder, APScheduler)
```

---

## ⚡ Diretrizes Técnicas Obrigatórias

### 1. Hashing de Senha e JWT (Sem Passlib)
- Usar a biblioteca `bcrypt` diretamente (`bcrypt.hashpw`, `bcrypt.checkpw`). **Nunca use passlib**.
- Token JWT expira em 120 minutos (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- Header: `Authorization: Bearer <token>`.

### 2. Timezone Institucional (`America/Fortaleza`)
- Usar funções do `app/core/timezone.py` (`now_in_app_timezone()`).
- **Proibido**: Usar `datetime.utcnow()` ou `datetime.now()` ingênuo.

### 3. Soft Delete e Índices Únicos Parciais
- A exclusão física é proibida (`inativo = True`).
- Para evitar erros `DuplicateKeyError` no PostgreSQL ao reativar ou recriar dados, **toda restrição de unicidade em tabelas com soft delete deve usar Índices Parciais**:
  ```python
  Index(
      'uix_diario_item_active',
      'id_diario_config', 'id_atribuicao_usuario', 'data_diario',
      unique=True,
      postgresql_where=text("inativo = false"),
      sqlite_where=text("inativo = false")
  )
  ```

### 4. `NivelCodigoEnum` contra Magic Numbers
- Não usar inteiros puros (`101`, `201`, `202`) no código. Usar a enum `NivelCodigoEnum`:
  - `NivelCodigoEnum.CHEFE_UNIDADE` (`101`)
  - `NivelCodigoEnum.GESTOR_GRUPO` (`201`)
  - `NivelCodigoEnum.PARTICIPANTE` (`202`)

### 5. Motor de Agendamentos (APScheduler)
- O motor de cron jobs é gerenciado em `app/services/scheduler_service.py` e iniciado/encerrado no `lifespan` de `app/main.py`.
- Lê agendamentos ativos, cria cron triggers e registra a execução em `agendamentos_historico`.

### 6. Herança de Configuração de Diário
- `DiarioConfig` possui relacionamento opcional com `GrupoTrabalho` (`id_grupo`) e `Unidade` (`id_unidade`).
- O serviço `daily_config_service.py` resolve primeiro a configuração do grupo e, caso inexistente, busca a configuração herdada da `Unidade`.

### 7. Isolamento Estrito de Multi-Tenancy e Segurança de Organizações
- **Validação e Extração de Contexto**: As dependências `require_active_organization` e `get_current_organization_id` em `app/core/dependencies.py` leem `X-Organization-Id` (header) e validam:
  1. Formato estrito de UUID v4.
  2. Existência e status ativo da organização (`inativo == False`).
  3. Existência de vínculo ativo do usuário (`UsuarioOrganizacao.inativo == False`), exceto para administradores da plataforma.
- **Proteção Anti-Tampering / Tenant Hopping**: Se um usuário comum tentar enviar o ID de outra organização à qual não pertence, a API rejeita com `HTTP 403 Forbidden` (`authorization.organization_member_required`).
- **Filtro Rigoroso**: É expressamente proibido usar `is_(None)` como fallback permissivo nas consultas de recursos (`Unidade`, `GrupoTrabalho`, `Usuario`, `Atribuicao`, `Perfil`). Apenas dados vinculados à organização solicitada devem ser retornados.
- **Validação de Atribuição**: Ao criar ou editar grupos, todos os usuários (chefes e participantes) devem obrigatoriamente possuir vínculo ativo com a organização do grupo (`UsuarioOrganizacao`).

### 8. Migrações de Banco (Alembic)
- Qualquer alteração nos arquivos de `app/models/` exige a criação de uma migração em `alembic/versions/`.
  ```bash
  poetry run alembic revision -m "nome_da_migracao"
  poetry run alembic upgrade head
  ```

### 9. Internacionalização de Respostas Públicas
- Todo texto exposto pela API deve ser uma chave explícita dos catálogos `app/i18n/locales/pt-BR.json` e `en-US.json`; nunca use texto literal em `HTTPException.detail`, `success_response` ou `error_response`.
- Mantenha os dois catálogos com exatamente as mesmas chaves e placeholders de interpolação. O teste `tests/test_i18n.py` valida paridade, referências estáticas e chaves órfãs.
- Reutilize chaves existentes para frases de mesma semântica. Só adicione uma nova chave quando a regra de negócio ou o contexto realmente diferir.
- Erros devem manter chaves no serviço/router; `app/core/exceptions.py` é o único limite que os converte em `message` e `detail` localizados conforme `Accept-Language`, além de definir `Content-Language`.
- Para erros com valores dinâmicos, use `detail={"key": "dominio.chave", "params": {"nome": valor}}`; não monte textos com f-strings no serviço/router.
- Nunca exponha `str(exc)`, logs, mensagens de bibliotecas ou detalhes de infraestrutura ao cliente. Use `common.internal_error` para falhas inesperadas.
- Descrições OpenAPI são avaliadas na criação do schema e usam o locale padrão; não alegue que `/openapi.json` muda por `Accept-Language` sem implementar um endpoint de schema localizado.

---

## 🧪 Validação e Execução

```bash
# Executar servidor local de desenvolvimento
poetry run dev

# Rodar os testes automatizados (Local / Poetry)
poetry run pytest

# Testes com cobertura (Local / Poetry)
poetry run pytest --cov=app --cov-report=term-missing

# Checagem de tipos estáticos
poetry run pyrefly check

# Executar testes via Docker (Ambiente isolado com Dockerfile.dev)
docker compose -f docker-compose.test.yml run --rm test
```

---

## ⚠️ Regras Invioláveis

1. **Nunca** use `passlib` — use `bcrypt` diretamente.
2. **Nunca** use `datetime.utcnow()` — use `now_in_app_timezone()`.
3. **Nunca** delete fisicamente do banco — use soft delete (`inativo = True`).
4. **Nunca** permita vazamento de dados entre organizações (use sempre isolamento estrito via `id_organizacao` / `X-Organization-Id`, sem fallbacks para `is_(None)`).
5. **Sempre** use índices únicos parciais (`WHERE inativo = false`) para chaves únicas.
6. **Sempre** crie uma migração Alembic para alterações em `app/models/`.
7. **Sempre** execute `pytest` antes de finalizar uma tarefa no backend.
8. **Sempre** pense e implemente novas funcionalidades ou alterações com internacionalização (i18n), mantendo paridade estrita entre `pt-BR.json` e `en-US.json` e sem mensagens literais no código.
