from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.services import agendamento_service

router = APIRouter(dependencies=[Depends(require_admin)])

@router.get("/")
def list_agendamentos(page: int = 0, size: int = 10, db: Session = Depends(get_db)):
    data = agendamento_service.list_all(db, page, size)
    return {"success": True, "message": "Agendamentos retrieved", "data": data}

@router.get("/{id}")
def get_agendamento(id: str, db: Session = Depends(get_db)):
    data = agendamento_service.get_by_id(db, id)
    return {"success": True, "message": "Agendamento retrieved", "data": data}

@router.post("/")
def create_agendamento(payload: dict, db: Session = Depends(get_db)):
    data = agendamento_service.create(db, payload)
    return {"success": True, "message": "Agendamento created", "data": data}

@router.put("/{id}")
def update_agendamento(id: str, payload: dict, db: Session = Depends(get_db)):
    data = agendamento_service.update(db, id, payload)
    return {"success": True, "message": "Agendamento updated", "data": data}

@router.put("/{id}/desativar")
def deactivate_agendamento(id: str, db: Session = Depends(get_db)):
    data = agendamento_service.deactivate(db, id)
    return {"success": True, "message": "Agendamento deactivated", "data": data}
