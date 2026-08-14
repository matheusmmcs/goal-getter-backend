from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.response import success_response
from app.models.usuario import Usuario
from app.services import daily_config_service, daily_permission_service
from app.schemas.daily import DiarioConfigCreate, DiarioConfigUpdate

router = APIRouter()

@router.get("/{config_id}")
def get_config(config_id: UUID, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    daily_permission_service.require_config_access(db, current_user, config_id)
    data = daily_config_service.get_config(db, config_id)
    return success_response(data=data, message="daily_config.retrieved")

@router.get("/grupo/{group_id}")
def get_config_by_group(group_id: UUID, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    daily_permission_service.require_group_access(db, current_user, group_id)
    data = daily_config_service.get_config_by_group(db, group_id, current_user)
    return success_response(data=data, message="daily_config.group_retrieved")

@router.post("/grupo/{group_id}")
def create_config(group_id: UUID, payload: DiarioConfigCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    daily_permission_service.require_config_edit_access(db, current_user, group_id)
    data = daily_config_service.create_config(db, group_id, payload)
    return success_response(data=data, message="daily_config.created")

@router.put("/{config_id}")
def update_config(config_id: UUID, payload: DiarioConfigUpdate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    daily_permission_service.require_config_access(db, current_user, config_id)
    config = db.query(daily_config_service.DiarioConfig).filter(daily_config_service.DiarioConfig.id == config_id, daily_config_service.DiarioConfig.inativo == False).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuração daily não encontrada")
    if config.id_grupo:
        daily_permission_service.require_config_edit_access(db, current_user, config.id_grupo)
    elif not current_user.is_admin:
        org_id = config.unidade.id_organizacao if config.unidade else None
        if not daily_permission_service.is_user_org_gestor(db, current_user.id, org_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Apenas Administradores ou Gestores da Organização podem editar configurações de unidade",
            )
    data = daily_config_service.update_config(db, config_id, payload)
    return success_response(data=data, message="daily_config.updated")
