from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_active_organization
from app.core.response import success_response
from app.models.usuario import Usuario
from app.models.organizacao import Organizacao
from app.models.enums import EntregaStatusEnum, OrigemEntregaEnum
from app.schemas.planejamento import EntregaCreate, EntregaUpdate
from app.services import entrega_service

router = APIRouter(tags=["Entregas"])


@router.get("/")
def list_entregas(
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    id_meta: UUID | None = Query(None),
    id_unidade: UUID | None = Query(None),
    id_usuario_responsavel: UUID | None = Query(None),
    status: EntregaStatusEnum | None = Query(None),
    tipo_origem: OrigemEntregaEnum | None = Query(None),
    q: str | None = Query(None),
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = entrega_service.list_all(
        db=db,
        id_organizacao=org.id,
        page=page,
        size=size,
        id_meta=id_meta,
        id_unidade=id_unidade,
        id_usuario_responsavel=id_usuario_responsavel,
        status_filter=status,
        tipo_origem=tipo_origem,
        q=q
    )
    return success_response(data=result, message="delivery.listed")


@router.get("/resumo-unidade")
def list_entregas_resumo_unidade(
    id_unidade: UUID | None = Query(None),
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = entrega_service.list_resumo_by_unidade(
        db=db,
        id_organizacao=org.id,
        id_unidade=id_unidade
    )
    return success_response(data=result, message="delivery.resumo_listed")


@router.get("/{id}")
def get_entrega(
    id: UUID,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = entrega_service.get_by_id(db=db, id_organizacao=org.id, entrega_id=id)
    return success_response(data=result, message="delivery.found")


@router.post("/")
def create_entrega(
    data: EntregaCreate,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = entrega_service.create(db=db, id_organizacao=org.id, data=data)
    return success_response(data=result, message="delivery.created")


@router.put("/{id}")
def update_entrega(
    id: UUID,
    data: EntregaUpdate,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = entrega_service.update(db=db, id_organizacao=org.id, entrega_id=id, data=data)
    return success_response(data=result, message="delivery.updated")


@router.put("/{id}/desativar")
def deactivate_entrega(
    id: UUID,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    entrega_service.deactivate(db=db, id_organizacao=org.id, entrega_id=id)
    return success_response(data=None, message="delivery.deactivated")
