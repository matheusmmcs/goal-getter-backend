from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user
from app.core.response import success_response
from app.services import petrvs_service

router = APIRouter(dependencies=[Depends(get_current_user)])

@router.get("/entregas/{cpf}")
async def get_entregas(cpf: str):
    data = await petrvs_service.get_entregas(cpf)
    return success_response(data=data, message="petrvs.entregas_retrieved")

@router.get("/entregas/ativas-hoje/{cpf}")
async def get_entregas_ativas_hoje(cpf: str):
    data = await petrvs_service.get_entregas_ativas_hoje(cpf)
    return success_response(data=data, message="petrvs.entregas_ativas_retrieved")
