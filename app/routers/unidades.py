from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin, get_current_organization_id
from app.core.response import success_response
from app.models.usuario import Usuario
from app.schemas.unidade import UnidadeCreate, UnidadeUpdate
from app.schemas.grupo import GrupoCreate, GrupoUpdate
from app.services import unidade_service, grupo_service

router = APIRouter(tags=["Unidades"])

@router.get("/")
def list_unidades(
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    id_organizacao: UUID | None = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = unidade_service.list_all(db, page, size, id_organizacao)
    return success_response(data=result, message="unit.listed")


@router.get("/{id}")
def get_unidade(id: UUID, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    result = unidade_service.get_by_id(db, id)
    return success_response(data=result, message="unit.found")

@router.post("/")
def create_unidade(
    data: UnidadeCreate,
    id_organizacao: UUID | None = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_admin)
):
    result = unidade_service.create(db, data, id_organizacao)
    return success_response(data=result, message="unit.created")

@router.put("/{id}")
def update_unidade(id: UUID, data: UnidadeUpdate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    result = unidade_service.update(db, id, data)
    return success_response(data=result, message="unit.updated")

@router.put("/{id}/desativar")
def deactivate_unidade(id: UUID, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    result = unidade_service.deactivate(db, id)
    return success_response(data=result, message="unit.deactivated")

@router.post("/{id}/grupos")
def create_grupo_in_unidade(id: UUID, data: GrupoCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    result = grupo_service.create_in_unidade(db, id, data)
    return success_response(data=result, message="group.created_in_unit")

@router.put("/{uid}/grupos/{gid}")
def update_grupo_in_unidade(uid: UUID, gid: UUID, data: GrupoUpdate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    result = grupo_service.update_in_unidade(db, uid, gid, data)
    return success_response(data=result, message="group.updated_in_unit")
