from typing import cast
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.atribuicao import Atribuicao
from app.models.diario_config import DiarioConfig
from app.models.enums import NivelCodigoEnum, PapelOrganizacaoEnum
from app.models.grupo import GrupoTrabalho
from app.models.nivel import Nivel
from app.models.perfil import Perfil
from app.models.usuario import Usuario
from app.models.usuario_organizacao import UsuarioOrganizacao


def get_group_org_id(db: Session, grupo: GrupoTrabalho) -> UUID | None:
    if grupo.id_organizacao:
        return cast(UUID, grupo.id_organizacao)
    if grupo.unidade and grupo.unidade.id_organizacao:
        return cast(UUID, grupo.unidade.id_organizacao)
    if grupo.id_unidade:
        from app.models.unidade import Unidade
        u = db.query(Unidade).filter(Unidade.id == grupo.id_unidade).first()
        if u and u.id_organizacao:
            return cast(UUID, u.id_organizacao)
    return None


def is_user_org_gestor(db: Session, user_id: UUID, org_id: UUID | None) -> bool:
    if not org_id:
        return False
    vinculo = (
        db.query(UsuarioOrganizacao)
        .filter(
            UsuarioOrganizacao.id_organizacao == org_id,
            UsuarioOrganizacao.id_usuario == user_id,
            UsuarioOrganizacao.inativo == False,
            UsuarioOrganizacao.papel_organizacao == PapelOrganizacaoEnum.GESTOR,
        )
        .first()
    )
    return vinculo is not None


def check_user_can_access_group(db: Session, current_user: Usuario, group_id: UUID) -> bool:
    """Verifica se o usuário tem permissão para visualizar/acessar um grupo de trabalho e seus diários."""
    if current_user.is_admin:
        return True

    grupo = db.query(GrupoTrabalho).filter(GrupoTrabalho.id == group_id, GrupoTrabalho.inativo == False).first()
    if not grupo:
        return False

    # 1. Gestor da Organização do grupo
    org_id = get_group_org_id(db, grupo)
    if is_user_org_gestor(db, cast(UUID, current_user.id), org_id):
        return True

    # 2. Membro do grupo (atribuição ativa como GESTOR_GRUPO ou PARTICIPANTE)
    atribuicao = (
        db.query(Atribuicao)
        .filter(
            Atribuicao.id_grupo == group_id,
            Atribuicao.id_usuario == current_user.id,
            Atribuicao.inativo == False,
        )
        .first()
    )
    if atribuicao:
        return True

    # 3. Chefe da Unidade pai do grupo
    if grupo.id_unidade:
        chefe_perfil = (
            db.query(Perfil)
            .join(Nivel, Perfil.id_nivel == Nivel.id)
            .filter(
                Perfil.id_unidade == grupo.id_unidade,
                Perfil.id_usuario == current_user.id,
                Perfil.inativo == False,
                Nivel.valor == NivelCodigoEnum.CHEFE_UNIDADE.value,
            )
            .first()
        )
        if chefe_perfil:
            return True

    return False


def check_user_can_access_config(db: Session, current_user: Usuario, config_id: UUID) -> bool:
    """Verifica se o usuário tem permissão para visualizar uma configuração de diário e seus itens."""
    if current_user.is_admin:
        return True

    config = db.query(DiarioConfig).filter(DiarioConfig.id == config_id, DiarioConfig.inativo == False).first()
    if not config:
        return False

    if config.id_grupo:
        return check_user_can_access_group(db, current_user, cast(UUID, config.id_grupo))

    if config.id_unidade:
        from app.models.unidade import Unidade
        unidade = db.query(Unidade).filter(Unidade.id == config.id_unidade).first()
        if unidade and is_user_org_gestor(db, cast(UUID, current_user.id), cast(UUID, unidade.id_organizacao)):
            return True
        chefe_perfil = (
            db.query(Perfil)
            .join(Nivel, Perfil.id_nivel == Nivel.id)
            .filter(
                Perfil.id_unidade == config.id_unidade,
                Perfil.id_usuario == current_user.id,
                Perfil.inativo == False,
                Nivel.valor == NivelCodigoEnum.CHEFE_UNIDADE.value,
            )
            .first()
        )
        if chefe_perfil:
            return True

        membro_grupo_unidade = (
            db.query(Atribuicao)
            .join(GrupoTrabalho, Atribuicao.id_grupo == GrupoTrabalho.id)
            .filter(
                GrupoTrabalho.id_unidade == config.id_unidade,
                Atribuicao.id_usuario == current_user.id,
                Atribuicao.inativo == False,
            )
            .first()
        )
        if membro_grupo_unidade:
            return True

    return False


def check_user_can_edit_config(db: Session, current_user: Usuario, group_id: UUID) -> bool:
    """Verifica se o usuário tem permissão para criar ou alterar a configuração do diário de um grupo.
    Apenas Administradores, Gestores da Organização, Chefes de Unidade ou Gestores do Grupo (código 201).
    """
    if current_user.is_admin:
        return True

    grupo = db.query(GrupoTrabalho).filter(GrupoTrabalho.id == group_id, GrupoTrabalho.inativo == False).first()
    if not grupo:
        return False

    # 1. Gestor da Organização
    org_id = get_group_org_id(db, grupo)
    if is_user_org_gestor(db, cast(UUID, current_user.id), org_id):
        return True

    # 2. Gestor do Grupo (nível 201)
    gestor_atribuicao = (
        db.query(Atribuicao)
        .join(Nivel, Atribuicao.id_nivel == Nivel.id)
        .filter(
            Atribuicao.id_grupo == group_id,
            Atribuicao.id_usuario == current_user.id,
            Atribuicao.inativo == False,
            Nivel.valor == NivelCodigoEnum.GESTOR_GRUPO.value,
        )
        .first()
    )
    if gestor_atribuicao:
        return True

    # 3. Chefe da Unidade (nível 101)
    if grupo.id_unidade:
        chefe_perfil = (
            db.query(Perfil)
            .join(Nivel, Perfil.id_nivel == Nivel.id)
            .filter(
                Perfil.id_unidade == grupo.id_unidade,
                Perfil.id_usuario == current_user.id,
                Perfil.inativo == False,
                Nivel.valor == NivelCodigoEnum.CHEFE_UNIDADE.value,
            )
            .first()
        )
        if chefe_perfil:
            return True

    return False


def require_group_access(db: Session, current_user: Usuario, group_id: UUID):
    if not check_user_can_access_group(db, current_user, group_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="authorization.group_access_denied",
        )


def require_config_access(db: Session, current_user: Usuario, config_id: UUID):
    if not check_user_can_access_config(db, current_user, config_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="authorization.daily_config_access_denied",
        )


def require_config_edit_access(db: Session, current_user: Usuario, group_id: UUID):
    if not check_user_can_edit_config(db, current_user, group_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="authorization.daily_config_edit_denied",
        )
