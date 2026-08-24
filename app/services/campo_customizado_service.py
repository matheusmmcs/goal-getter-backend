from uuid import UUID
from typing import Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.organizacao_campo_customizado import OrganizacaoCampoCustomizado
from app.models.usuario_organizacao import UsuarioOrganizacao
from app.models.unidade import Unidade
from app.models.enums import EntidadeCampoCustomizadoEnum
from app.schemas.campo_customizado import (
    OrganizacaoCampoCustomizadoCreate,
    OrganizacaoCampoCustomizadoUpdate,
)
from app.core.timezone import now_in_app_timezone


def list_campos_customizados(
    db: Session,
    id_organizacao: UUID,
    entidade: Optional[EntidadeCampoCustomizadoEnum] = None,
) -> list[OrganizacaoCampoCustomizado]:
    query = db.query(OrganizacaoCampoCustomizado).filter(
        OrganizacaoCampoCustomizado.id_organizacao == id_organizacao,
        OrganizacaoCampoCustomizado.inativo == False,
        OrganizacaoCampoCustomizado.ativo == True,
    )
    if entidade:
        query = query.filter(OrganizacaoCampoCustomizado.entidade == entidade)
    return query.order_by(OrganizacaoCampoCustomizado.nome_campo.asc()).all()


def get_campo_customizado(
    db: Session,
    id_organizacao: UUID,
    id_campo: UUID,
) -> OrganizacaoCampoCustomizado:
    campo = db.query(OrganizacaoCampoCustomizado).filter(
        OrganizacaoCampoCustomizado.id == id_campo,
        OrganizacaoCampoCustomizado.id_organizacao == id_organizacao,
        OrganizacaoCampoCustomizado.inativo == False,
    ).first()
    if not campo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="campo_customizado.not_found",
        )
    return campo


def create_campo_customizado(
    db: Session,
    id_organizacao: UUID,
    data: OrganizacaoCampoCustomizadoCreate,
) -> OrganizacaoCampoCustomizado:
    # Check key uniqueness within organization for active fields
    existing = db.query(OrganizacaoCampoCustomizado).filter(
        OrganizacaoCampoCustomizado.id_organizacao == id_organizacao,
        OrganizacaoCampoCustomizado.entidade == data.entidade,
        OrganizacaoCampoCustomizado.chave == data.chave.strip(),
        OrganizacaoCampoCustomizado.inativo == False,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="campo_customizado.chave_duplicate",
        )

    campo = OrganizacaoCampoCustomizado(
        id_organizacao=id_organizacao,
        entidade=data.entidade,
        nome_campo=data.nome_campo.strip(),
        chave=data.chave.strip(),
        tipo_dado=data.tipo_dado,
        obrigatorio=data.obrigatorio,
        descricao=data.descricao,
        inativo=False,
        ativo=True,
    )
    db.add(campo)
    db.commit()
    db.refresh(campo)
    return campo


def update_campo_customizado(
    db: Session,
    id_organizacao: UUID,
    id_campo: UUID,
    data: OrganizacaoCampoCustomizadoUpdate,
) -> OrganizacaoCampoCustomizado:
    campo = get_campo_customizado(db, id_organizacao, id_campo)
    if data.nome_campo is not None:
        campo.nome_campo = data.nome_campo.strip()
    if data.tipo_dado is not None:
        campo.tipo_dado = data.tipo_dado
    if data.obrigatorio is not None:
        campo.obrigatorio = data.obrigatorio
    if data.descricao is not None:
        campo.descricao = data.descricao
    campo.updated_at = now_in_app_timezone()
    db.commit()
    db.refresh(campo)
    return campo


def delete_campo_customizado(
    db: Session,
    id_organizacao: UUID,
    id_campo: UUID,
) -> bool:
    campo = get_campo_customizado(db, id_organizacao, id_campo)
    campo.inativo = True
    campo.ativo = False
    campo.updated_at = now_in_app_timezone()
    db.commit()
    return True


def get_usuario_campos_customizados(
    db: Session,
    id_organizacao: UUID,
    id_usuario: UUID,
) -> dict[str, Any]:
    vinculo = db.query(UsuarioOrganizacao).filter(
        UsuarioOrganizacao.id_organizacao == id_organizacao,
        UsuarioOrganizacao.id_usuario == id_usuario,
        UsuarioOrganizacao.inativo == False,
    ).first()
    if not vinculo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="organization.user_link_not_found",
        )
    return dict(vinculo.campos_customizados or {})


def update_usuario_campos_customizados(
    db: Session,
    id_organizacao: UUID,
    id_usuario: UUID,
    novos_valores: dict[str, Any],
) -> dict[str, Any]:
    vinculo = db.query(UsuarioOrganizacao).filter(
        UsuarioOrganizacao.id_organizacao == id_organizacao,
        UsuarioOrganizacao.id_usuario == id_usuario,
        UsuarioOrganizacao.inativo == False,
    ).first()
    if not vinculo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="organization.user_link_not_found",
        )
    current = dict(vinculo.campos_customizados or {})
    current.update(novos_valores)
    vinculo.campos_customizados = current
    vinculo.updated_at = now_in_app_timezone()
    db.commit()
    return current


def get_unidade_campos_customizados(
    db: Session,
    id_organizacao: UUID,
    id_unidade: UUID,
) -> dict[str, Any]:
    unidade = db.query(Unidade).filter(
        Unidade.id == id_unidade,
        Unidade.id_organizacao == id_organizacao,
        Unidade.inativo == False,
    ).first()
    if not unidade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="unit.not_found",
        )
    return dict(unidade.campos_customizados or {})


def update_unidade_campos_customizados(
    db: Session,
    id_organizacao: UUID,
    id_unidade: UUID,
    novos_valores: dict[str, Any],
) -> dict[str, Any]:
    unidade = db.query(Unidade).filter(
        Unidade.id == id_unidade,
        Unidade.id_organizacao == id_organizacao,
        Unidade.inativo == False,
    ).first()
    if not unidade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="unit.not_found",
        )
    current = dict(unidade.campos_customizados or {})
    current.update(novos_valores)
    unidade.campos_customizados = current
    unidade.updated_at = now_in_app_timezone()
    db.commit()
    return current
