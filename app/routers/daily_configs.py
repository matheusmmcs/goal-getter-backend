from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.services import daily_config_service

router = APIRouter()

@router.get("/{config_id}")
def get_config(config_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    data = daily_config_service.get_config(db, config_id)
    return {"success": True, "message": "Config retrieved", "data": data}

@router.get("/grupo/{group_id}")
def get_config_by_group(group_id: str, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    data = daily_config_service.get_config_by_group(db, group_id, str(current_user.id))
    return {"success": True, "message": "Config retrieved for group", "data": data}
