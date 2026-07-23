from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services import grupo_service

router = APIRouter(tags=["Grupos"])

@router.get("/")
def list_grupos(
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = grupo_service.list_all(db, page, size)
    return {"success": True, "message": "Grupos listados", "data": result}

@router.get("/{id}")
def get_grupo(id: str, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    result = grupo_service.get_by_id(db, id)
    return {"success": True, "message": "Grupo encontrado", "data": result}

@router.put("/{id}/desativar")
def deactivate_grupo(id: str, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    result = grupo_service.deactivate(db, id)
    return {"success": True, "message": "Grupo desativado", "data": result}
