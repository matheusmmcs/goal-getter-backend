from fastapi import APIRouter

router = APIRouter()

@router.get('/versionsys')
def get_version():
    """Retorna a versão do sistema."""
    return {"version": "1.0.0", "name": "Goal Getter API"}

@router.get('/environment')
def get_environment():
    """Retorna informações do ambiente."""
    return {"nodeEnv": "development", "environment": "dev"}
