from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin, get_current_organization_id
from app.core.response import success_response
from app.schemas.usuario import (
    UsuarioCreate,
    UsuarioDetailResponse,
    UsuarioResponse,
    UsuarioUpdate,
)
from app.services import usuario_service

router = APIRouter(tags=["Usuarios"])


@router.get("/")
def list_usuarios(
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    nome: str | None = Query(None),
    inativo: str | None = Query(None),
    include_inactive: bool = Query(True),
    id_organizacao: UUID | None = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = usuario_service.list_usuarios(
        db,
        page=page,
        size=size,
        nome=nome,
        inativo=inativo,
        include_inactive=include_inactive,
        id_organizacao=id_organizacao
    )
    result["items"] = [
        UsuarioResponse.model_validate(u).model_dump() for u in result["items"]
    ]
    return success_response(data=result, message="user.listed")


@router.get("/{id}")
def get_usuario(
    id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = usuario_service.get_by_id(db, id, include_inactive=True)
    return success_response(
        data=UsuarioDetailResponse.model_validate(result).model_dump(),
        message="user.found",
    )


@router.post("/")
def create_usuario(
    data: UsuarioCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    result = usuario_service.create(db, data)
    return success_response(
        data=UsuarioResponse.model_validate(result).model_dump(),
        message="user.created",
    )


@router.put("/{id}")
def update_usuario(
    id: UUID,
    data: UsuarioUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    result = usuario_service.update(db, id, data)
    return success_response(
        data=UsuarioResponse.model_validate(result).model_dump(),
        message="user.updated",
    )


@router.put("/{id}/desativar")
def deactivate_usuario(
    id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    result = usuario_service.deactivate(db, id)
    return success_response(
        data=UsuarioResponse.model_validate(result).model_dump(),
        message="user.deactivated",
    )


@router.put("/{id}/reativar")
def reactivate_usuario(
    id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    result = usuario_service.reactivate(db, id)
    return success_response(
        data=UsuarioResponse.model_validate(result).model_dump(),
        message="user.reactivated",
    )


@router.get("/{id}/atribuicoes")
def get_user_atribuicoes(
    id: UUID,
    id_organizacao: UUID | None = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = usuario_service.get_atribuicoes(db, id, id_organizacao)
    return success_response(data=result, message="user.atribuicoes_found")


@router.get("/{id}/perfis")
def get_user_perfis(
    id: UUID,
    id_organizacao: UUID | None = Depends(get_current_organization_id),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = usuario_service.get_perfis(db, id, id_organizacao)
    return success_response(data=result, message="user.perfis_found")
