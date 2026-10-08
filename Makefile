.DEFAULT_GOAL := help

# ==============================================================================
# Goal Getter Backend — Makefile de Automação de Desenvolvimento
# ==============================================================================

PYTHON ?= poetry run python
ALEMBIC ?= poetry run alembic
PYTEST ?= poetry run pytest
PYREFLY ?= poetry run pyrefly
UVICORN ?= poetry run uvicorn
DOCKER_COMPOSE ?= docker compose


# Cores para o help interativo
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m

.PHONY: help
help: ## Mostra esta lista de comandos disponíveis
	@echo "$(CYAN)========================================================================$(RESET)"
	@echo "$(CYAN)           Goal Getter Backend — Comandos de Desenvolvimento           $(RESET)"
	@echo "$(CYAN)========================================================================$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'

## === 🚀 Execução & Desenvolvimento ===

.PHONY: dev
dev: ## Sobe a stack de desenvolvimento (API + DB) via Docker Compose com hot reload (porta 8881)
	$(DOCKER_COMPOSE) up

.PHONY: dev-d
dev-d: ## Sobe a stack de desenvolvimento via Docker em background (detached)
	$(DOCKER_COMPOSE) up -d

.PHONY: dev-local
dev-local: ## Inicia a API FastAPI localmente via Poetry/Uvicorn sem Docker (porta 8000)
	$(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000



.PHONY: db
db: ## Sobe apenas o container do PostgreSQL em background (porta 5472)
	$(DOCKER_COMPOSE) up db -d

.PHONY: db-down
db-down: ## Para o container do PostgreSQL
	$(DOCKER_COMPOSE) stop db

.PHONY: up
up: ## Sobe a stack completa (API + DB) via Docker Compose em background
	$(DOCKER_COMPOSE) up -d

.PHONY: up-build
up-build: ## Reconstrói as imagens e sobe a stack Docker completa
	$(DOCKER_COMPOSE) up --build -d

.PHONY: down
down: ## Para e remove os containers da stack Docker
	$(DOCKER_COMPOSE) down

.PHONY: restart
restart: ## Reinicia os containers da stack Docker
	$(DOCKER_COMPOSE) restart

.PHONY: logs
logs: ## Exibe logs em tempo real de todos os containers
	$(DOCKER_COMPOSE) logs -f

.PHONY: logs-backend
logs-backend: ## Exibe logs em tempo real apenas da API backend
	$(DOCKER_COMPOSE) logs -f backend

.PHONY: logs-db
logs-db: ## Exibe logs em tempo real apenas do banco de dados
	$(DOCKER_COMPOSE) logs -f db

.PHONY: ps
ps: ## Lista status dos containers Docker da stack
	$(DOCKER_COMPOSE) ps

## === 🗄️ Banco de Dados & Migrações (Alembic) ===

.PHONY: migrate
migrate: ## Executa as migrações pendentes no banco (alembic upgrade head)
	$(ALEMBIC) upgrade head

.PHONY: migrate-create
migrate-create: ## Cria uma nova migração autogerada (Uso: make migrate-create m="mensagem")
	@if [ -z "$(m)" ]; then \
		echo "$(YELLOW)Aviso: Especifique a mensagem da migração. Ex: make migrate-create m=\"adicionar_campo\"$(RESET)"; \
		exit 1; \
	fi
	$(ALEMBIC) revision --autogenerate -m "$(m)"

.PHONY: migrate-empty
migrate-empty: ## Cria uma migração em branco para SQL manual (Uso: make migrate-empty m="mensagem")
	@if [ -z "$(m)" ]; then \
		echo "$(YELLOW)Aviso: Especifique a mensagem da migração. Ex: make migrate-empty m=\"ajuste_manual\"$(RESET)"; \
		exit 1; \
	fi
	$(ALEMBIC) revision -m "$(m)"

.PHONY: migrate-down
migrate-down: ## Desfaz a última migração aplicada (alembic downgrade -1)
	$(ALEMBIC) downgrade -1

.PHONY: migrate-history
migrate-history: ## Exibe o histórico de revisões de migração
	$(ALEMBIC) history --verbose

.PHONY: migrate-current
migrate-current: ## Exibe a versão atual da revisão de banco aplicada
	$(ALEMBIC) current

.PHONY: db-seed
db-seed: ## Executa o seeder de dados iniciais (admin, níveis, UFPI)
	$(PYTHON) -c "from app.seeder import run_seed; run_seed()"

.PHONY: db-reset
db-reset: ## Reinicia o banco de dados Docker do zero, roda migrações e seed
	@echo "$(YELLOW)Reiniciando banco de dados PostgreSQL...$(RESET)"
	$(DOCKER_COMPOSE) down -v
	$(DOCKER_COMPOSE) up db -d
	@echo "Aguardando PostgreSQL iniciar..."
	@sleep 3
	$(ALEMBIC) upgrade head
	$(PYTHON) -c "from app.seeder import run_seed; run_seed()"
	@echo "$(GREEN)Banco reiniciado e preparado com sucesso!$(RESET)"

## === 🧪 Testes & Qualidade ===

.PHONY: test
test: ## Executa a suíte de testes com Pytest
	$(PYTEST)

.PHONY: test-v
test-v: ## Executa testes com saída detalhada (-v)
	$(PYTEST) -v

.PHONY: test-cov
test-cov: ## Executa testes com relatório de cobertura de código
	$(PYTEST) --cov=app --cov-report=term-missing

.PHONY: test-docker
test-docker: ## Executa testes no ambiente isolado Docker (Dockerfile.dev)
	$(DOCKER_COMPOSE) -f docker-compose.test.yml run --rm test

.PHONY: lint
lint: ## Executa checagem de tipos estáticos com Pyrefly
	$(PYREFLY) check

.PHONY: check
check: lint test ## Executa validação completa (checagem de tipos + testes)

## === 📦 Dependências & Setup ===

.PHONY: install
install: ## Instala dependências do projeto via Poetry
	poetry install

.PHONY: setup
setup: ## Configuração inicial completa do ambiente de desenvolvimento
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(GREEN)Arquivo .env criado a partir de .env.example.$(RESET)"; \
	fi
	poetry install
	$(DOCKER_COMPOSE) up db -d
	@sleep 3
	$(ALEMBIC) upgrade head
	@echo "$(GREEN)Ambiente backend configurado com sucesso! Use 'make dev' para iniciar.$(RESET)"

.PHONY: clean
clean: ## Remove arquivos temporários, caches de build, pytest e coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.py[cod]" -delete 2>/dev/null || true
	rm -rf .pytest_cache .coverage htmlcov coverage.xml

## === 🤖 IA & Contexto (Repomix & CodeGraph) ===

.PHONY: repomix
repomix: ## Empacota o contexto do backend usando Repomix
	npx -y repomix

.PHONY: codegraph-init
codegraph-init: ## Inicializa o índice do CodeGraph no backend
	npx -y @colbymchenry/codegraph init

.PHONY: codegraph-index
codegraph-index: ## Reconstrói todo o índice do CodeGraph do zero
	npx -y @colbymchenry/codegraph index

.PHONY: codegraph-sync
codegraph-sync: ## Sincroniza incrementalmente o índice do CodeGraph
	npx -y @colbymchenry/codegraph sync

.PHONY: context
context: ## Atualiza/inicializa o contexto completo de IA (CodeGraph sync/init + Repomix)
	@echo "$(CYAN)=== Atualizando Contexto de IA (CodeGraph & Repomix) ===$(RESET)"
	@if [ ! -d ".codegraph" ]; then \
		echo "$(YELLOW)Inicializando CodeGraph...$(RESET)"; \
		npx -y @colbymchenry/codegraph init; \
	else \
		echo "$(GREEN)Sincronizando índice do CodeGraph...$(RESET)"; \
		npx -y @colbymchenry/codegraph sync; \
	fi
	@echo "$(GREEN)Empacotando contexto com Repomix...$(RESET)"
	npx -y repomix
	@echo "$(GREEN)Contexto atualizado com sucesso!$(RESET)"

.PHONY: ai-context
ai-context: context ## Alias para make context

.PHONY: codegraph-status
codegraph-status: ## Exibe o status atual do índice CodeGraph
	npx -y @colbymchenry/codegraph status

