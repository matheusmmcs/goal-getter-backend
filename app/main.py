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
    Base.metadata.create_all(bind=engine)
    if settings.DB_RUN_SEED:
        from app.seeder import run_seed
        run_seed()
    yield
    # Shutdown

app = FastAPI(title='Goal Getter API', version='1.0.0', lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Import and register all routers
from app.routers import auth, usuarios, unidades, niveis, grupos, daily_configs, daily_items, agendamentos, petrvs

app.include_router(auth.router, prefix='/api/auth', tags=['Auth'])
app.include_router(usuarios.router, prefix='/api/usuarios', tags=['Usuarios'])
app.include_router(unidades.router, prefix='/api/unidades', tags=['Unidades'])
app.include_router(niveis.router, prefix='/api/niveis', tags=['Niveis'])
app.include_router(grupos.router, prefix='/api/grupos', tags=['Grupos'])
app.include_router(daily_configs.router, prefix='/api/daily/configs', tags=['Daily Configs'])
app.include_router(daily_items.router, prefix='/api/daily/configs', tags=['Daily Items'])
app.include_router(agendamentos.router, prefix='/api/daily/agendamentos', tags=['Agendamentos'])
app.include_router(petrvs.router, prefix='/api/petrvs', tags=['Petrvs'])
