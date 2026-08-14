from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin, require_org_gestor, require_org_member
from app.core.response import success_response
from app.models.usuario import Usuario
from app.schemas.organizacao import (
    OrganizacaoCreate,
    OrganizacaoUpdate,
    UsuarioVinculoItem,
    VinculoUpdateSchema,
)
from app.services import organizacao_service

router = APIRouter(prefix="/organizacoes", tags=["Organizações"])


@router.get("/")
def list_organizacoes(
    page: int = Query(0, ge=0),
    size: int = Query(50, ge=1, le=100),
    include_inativos: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = organizacao_service.list_organizacoes_for_user(db, current_user, page, size, include_inativos)
    return success_response(data=result, message="organization.listed")



@router.get("/{id}")
def get_organizacao(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = organizacao_service.get_detail_by_id(db, id)
    return success_response(data=result, message="organization.found")


@router.post("/")
def create_organizacao(
    data: OrganizacaoCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = organizacao_service.create_organizacao(db, data, current_user=current_user)
    return success_response(data=result, message="organization.created")


@router.put("/{id}")
def update_organizacao(
    id: UUID,
    data: OrganizacaoUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_admin)
):
    result = organizacao_service.update_organizacao(db, id, data)
    return success_response(data=result, message="organization.updated")


@router.put("/{id}/desativar")
def deactivate_organizacao(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_admin)
):
    result = organizacao_service.deactivate_organizacao(db, id)
    return success_response(data=result, message="organization.deactivated")


# --- VÍNCULOS DE USUÁRIOS NA ORGANIZAÇÃO ---

@router.get("/{id}/usuarios")
def list_usuarios_organizacao(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    require_org_member(str(id), current_user, db)
    result = organizacao_service.listar_usuarios_detalhados_organizacao(db, id)
    return success_response(data=result, message="organization.users.listed")


@router.get("/{id}/usuarios-disponiveis")
def list_usuarios_disponiveis_organizacao(
    id: UUID,
    nome: str | None = Query(None),
    page: int = Query(0, ge=0),
    size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    require_org_gestor(str(id), current_user, db)
    result = organizacao_service.listar_usuarios_disponiveis_organizacao(db, id, nome, page, size)
    return success_response(data=result, message="organization.available_users.listed")


@router.post("/{id}/vinculos")
def adicionar_vinculo(
    id: UUID,
    data: UsuarioVinculoItem,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    require_org_gestor(str(id), current_user, db)
    result = organizacao_service.adicionar_vinculo_usuario(db, id, data)
    return success_response(data=result, message="organization.vinculo.created")


@router.put("/{id}/vinculos/{usuario_id}")
def atualizar_vinculo(
    id: UUID,
    usuario_id: UUID,
    data: VinculoUpdateSchema,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    require_org_gestor(str(id), current_user, db)
    result = organizacao_service.atualizar_vinculo_usuario(db, id, usuario_id, data)
    return success_response(data=result, message="organization.vinculo.updated")


@router.put("/{id}/vinculos/{usuario_id}/desativar")
def desativar_vinculo(
    id: UUID,
    usuario_id: UUID,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    require_org_gestor(str(id), current_user, db)
    result = organizacao_service.desativar_vinculo_usuario(db, id, usuario_id)
    return success_response(data=result, message="organization.vinculo.deactivated")
