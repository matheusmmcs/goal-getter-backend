from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.response import success_response
from app.models.usuario import Usuario
from app.services import grupo_service

router = APIRouter(tags=["Grupos"])

@router.get("/")
def list_grupos(
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = grupo_service.list_all(db, page, size)
    return success_response(data=result, message="group.listed")

@router.get("/{id}")
def get_grupo(id: UUID, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    result = grupo_service.get_by_id(db, id)
    return success_response(data=result, message="group.found")

@router.put("/{id}/desativar")
def deactivate_grupo(id: UUID, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    result = grupo_service.deactivate(db, id)
    return success_response(data=result, message="group.deactivated")
