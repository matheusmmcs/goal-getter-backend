from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user
from app.services import petrvs_service

router = APIRouter(dependencies=[Depends(get_current_user)])

@router.get("/entregas/{cpf}")
async def get_entregas(cpf: str):
    data = await petrvs_service.get_entregas(cpf)
    return {"success": True, "message": "Entregas retrieved", "data": data}

@router.get("/entregas/ativas-hoje/{cpf}")
async def get_entregas_ativas_hoje(cpf: str):
    data = await petrvs_service.get_entregas_ativas_hoje(cpf)
    return {"success": True, "message": "Entregas ativas hoje retrieved", "data": data}
