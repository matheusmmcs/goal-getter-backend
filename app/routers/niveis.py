from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.schemas.nivel import NivelCreate, NivelUpdate
from app.services import nivel_service

router = APIRouter(tags=["Niveis"])

@router.get("/")
def list_niveis(
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    result = nivel_service.list_all(db, page, size)
    return {"success": True, "message": "Níveis listados", "data": result}

@router.post("/")
def create_nivel(data: NivelCreate, db: Session = Depends(get_db), current_user = Depends(require_admin)):
    result = nivel_service.create(db, data)
    return {"success": True, "message": "Nível criado", "data": result}

@router.put("/{id}")
def update_nivel(id: str, data: NivelUpdate, db: Session = Depends(get_db), current_user = Depends(require_admin)):
    result = nivel_service.update(db, id, data)
    return {"success": True, "message": "Nível atualizado", "data": result}

@router.put("/{id}/desativar")
def deactivate_nivel(id: str, db: Session = Depends(get_db), current_user = Depends(require_admin)):
    result = nivel_service.deactivate(db, id)
    return {"success": True, "message": "Nível desativado", "data": result}
