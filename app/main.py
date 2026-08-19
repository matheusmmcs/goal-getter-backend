from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import engine, Base
from app.core.logging import setup_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    if settings.DB_RUN_MIGRATIONS:
        try:
            import logging
            from alembic.config import Config
            from alembic import command
            alembic_cfg = Config("alembic.ini")
            alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
            command.upgrade(alembic_cfg, "head")
            logging.getLogger("alembic").info("Alembic database migrations applied successfully.")
        except Exception as e:
            import logging
            logging.getLogger("alembic").error(f"Error during Alembic auto-upgrade: {e}", exc_info=True)



    Base.metadata.create_all(bind=engine)
    if settings.DB_RUN_SEED:
        from app.seeder import run_seed
        run_seed()

    # Iniciar motor de agendamentos (scheduler)
    try:
        from app.services.scheduler_service import start_scheduler, shutdown_scheduler
        start_scheduler()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Erro ao inicializar motor de agendamentos: {e}", exc_info=True)

    yield

    # Shutdown
    try:
        from app.services.scheduler_service import shutdown_scheduler
        shutdown_scheduler()
    except Exception:
        pass

from fastapi import Request
from app.core.exceptions import setup_exception_handlers
from app.core.i18n import parse_accept_language, set_current_locale, reset_current_locale

app = FastAPI(title='Goal Getter API', version='1.0.0', lifespan=lifespan)
setup_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:5173',
        'http://localhost:3000',
        'http://localhost:8080',
        'http://localhost:8084',
        'http://127.0.0.1:5173',
        'http://127.0.0.1:3000',
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

@app.middleware("http")
async def i18n_middleware(request: Request, call_next):
    accept_lang = request.headers.get("Accept-Language")
    locale = parse_accept_language(accept_lang)
    token = set_current_locale(locale)
    try:
        response = await call_next(request)
        response.headers["Content-Language"] = locale
        return response
    finally:
        reset_current_locale(token)

# Import and register all routers
from app.routers import auth, usuarios, unidades, niveis, grupos, daily_configs, daily_items, agendamentos, petrvs, organizacoes, system, metas, entregas, integracoes

app.include_router(auth.router, prefix='/api/auth', tags=['Auth'])
app.include_router(system.router, prefix='/api', tags=['System'])
app.include_router(organizacoes.router, prefix='/api', tags=['Organizações'])
app.include_router(usuarios.router, prefix='/api/usuarios', tags=['Usuarios'])
app.include_router(unidades.router, prefix='/api/unidades', tags=['Unidades'])
app.include_router(niveis.router, prefix='/api/niveis', tags=['Niveis'])
app.include_router(grupos.router, prefix='/api/grupos', tags=['Grupos'])
app.include_router(metas.router, prefix='/api/metas', tags=['Metas'])
app.include_router(entregas.router, prefix='/api/entregas', tags=['Entregas'])
app.include_router(integracoes.router, prefix='/api/integracoes', tags=['Integrações'])
app.include_router(daily_configs.router, prefix='/api/daily/configs', tags=['Daily Configs'])
app.include_router(daily_items.router, prefix='/api/daily/configs', tags=['Daily Items'])
app.include_router(agendamentos.router, prefix='/api/daily/agendamentos', tags=['Agendamentos'])
app.include_router(petrvs.router, prefix='/api/petrvs', tags=['Petrvs'])



