from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.response import success_response
from app.models.usuario import Usuario
from app.services import daily_config_service
from app.schemas.daily import DiarioConfigCreate, DiarioConfigUpdate

router = APIRouter()

@router.get("/{config_id}")
def get_config(config_id: UUID, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    data = daily_config_service.get_config(db, config_id)
    return success_response(data=data, message="daily_config.retrieved")

@router.get("/grupo/{group_id}")
def get_config_by_group(group_id: UUID, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    data = daily_config_service.get_config_by_group(db, group_id, current_user.id)
    return success_response(data=data, message="daily_config.group_retrieved")

@router.post("/grupo/{group_id}")
def create_config(group_id: UUID, payload: DiarioConfigCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    data = daily_config_service.create_config(db, group_id, payload)
    return success_response(data=data, message="daily_config.created")

@router.put("/{config_id}")
def update_config(config_id: UUID, payload: DiarioConfigUpdate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    data = daily_config_service.update_config(db, config_id, payload)
    return success_response(data=data, message="daily_config.updated")
