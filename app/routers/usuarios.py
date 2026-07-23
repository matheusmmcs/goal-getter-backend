from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.schemas.usuario import (
    UsuarioCreate,
    UsuarioResponse,
    UsuarioUpdate,
)
from app.services import usuario_service

router = APIRouter(tags=["Usuarios"])


@router.get("/")
def list_usuarios(
    page: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = usuario_service.list_active(db, page, size)
    result["items"] = [
        UsuarioResponse.model_validate(u).model_dump() for u in result["items"]
    ]
    return {"success": True, "message": "Usuários listados", "data": result}


@router.get("/{id}")
def get_usuario(
    id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = usuario_service.get_by_id(db, id)
    return {
        "success": True,
        "message": "Usuário encontrado",
        "data": UsuarioResponse.model_validate(result).model_dump(),
    }


@router.post("/")
def create_usuario(
    data: UsuarioCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    result = usuario_service.create(db, data)
    return {
        "success": True,
        "message": "Usuário criado",
        "data": UsuarioResponse.model_validate(result).model_dump(),
    }


@router.put("/{id}")
def update_usuario(
    id: UUID,
    data: UsuarioUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = usuario_service.update(db, id, data)
    return {
        "success": True,
        "message": "Usuário atualizado",
        "data": UsuarioResponse.model_validate(result).model_dump(),
    }


@router.put("/{id}/desativar")
def deactivate_usuario(
    id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = usuario_service.deactivate(db, id)
    return {
        "success": True,
        "message": "Usuário desativado",
        "data": UsuarioResponse.model_validate(result).model_dump(),
    }


@router.get("/{id}/atribuicoes")
def get_user_atribuicoes(
    id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = usuario_service.get_atribuicoes(db, id)
    return {"success": True, "message": "Atribuições encontradas", "data": result}


@router.get("/{id}/perfis")
def get_user_perfis(
    id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = usuario_service.get_perfis(db, id)
    return {"success": True, "message": "Perfis encontrados", "data": result}
