from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services import daily_config_service
from app.schemas.daily import DiarioConfigCreate, DiarioConfigUpdate

router = APIRouter()

@router.get("/{config_id}")
def get_config(config_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    data = daily_config_service.get_config(db, config_id)
    return {"success": True, "message": "Config retrieved", "data": data}

@router.get("/grupo/{group_id}")
def get_config_by_group(group_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    data = daily_config_service.get_config_by_group(db, group_id, str(current_user.id))
    return {"success": True, "message": "Config retrieved for group", "data": data}

@router.post("/grupo/{group_id}")
def create_config(group_id: str, payload: DiarioConfigCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    data = daily_config_service.create_config(db, UUID(group_id), payload)
    return {"success": True, "message": "Configuração criada com sucesso", "data": data}

@router.put("/{config_id}")
def update_config(config_id: str, payload: DiarioConfigUpdate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    data = daily_config_service.update_config(db, UUID(config_id), payload)
    return {"success": True, "message": "Configuração atualizada com sucesso", "data": data}

