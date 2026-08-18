from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_active_organization
from app.core.response import success_response
from app.models.usuario import Usuario
from app.models.organizacao import Organizacao
from app.models.enums import MetaStatusEnum
from app.schemas.planejamento import MetaCreate, MetaUpdate
from app.services import meta_service

router = APIRouter(tags=["Metas"])


@router.get("/")
def list_metas(
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    id_unidade: UUID | None = Query(None),
    status: MetaStatusEnum | None = Query(None),
    tipo_origem: str | None = Query(None),
    q: str | None = Query(None),
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = meta_service.list_all(
        db=db,
        id_organizacao=org.id,
        page=page,
        size=size,
        id_unidade=id_unidade,
        status_filter=status,
        tipo_origem=tipo_origem,
        q=q
    )
    return success_response(data=result, message="meta.listed")


@router.get("/{id}")
def get_meta(
    id: UUID,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = meta_service.get_by_id(db=db, id_organizacao=org.id, meta_id=id)
    return success_response(data=result, message="meta.found")


@router.post("/")
def create_meta(
    data: MetaCreate,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = meta_service.create(db=db, id_organizacao=org.id, data=data)
    return success_response(data=result, message="meta.created")


@router.put("/{id}")
def update_meta(
    id: UUID,
    data: MetaUpdate,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = meta_service.update(db=db, id_organizacao=org.id, meta_id=id, data=data)
    return success_response(data=result, message="meta.updated")


@router.put("/{id}/desativar")
def deactivate_meta(
    id: UUID,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    meta_service.deactivate(db=db, id_organizacao=org.id, meta_id=id)
    return success_response(data=None, message="meta.deactivated")
