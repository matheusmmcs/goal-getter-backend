from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.timezone import now_in_app_timezone
from app.models.atribuicao import Atribuicao
from app.models.diario_config import DiarioConfig
from app.models.diario_item import DiarioItem
from app.models.grupo import GrupoTrabalho


def get_config(db: Session, config_id: UUID):
    """Get detailed daily config with group and group's atribuições."""
    config = (
        db.query(DiarioConfig)
        .options(
            joinedload(DiarioConfig.grupo)
            .selectinload(GrupoTrabalho.atribuicoes)
            .joinedload(Atribuicao.usuario),
        )
        .filter(DiarioConfig.id == config_id, DiarioConfig.inativo == False)
        .first()
    )
    if not config:
        raise HTTPException(
            status_code=404, detail="Configuração daily não encontrada"
        )
    return config


def get_config_by_group(db: Session, group_id: UUID, current_user_id: UUID):
    """Get config summary for a group, including hasRegistroHoje for current user."""
    config = (
        db.query(DiarioConfig)
        .options(joinedload(DiarioConfig.grupo))
        .filter(
            DiarioConfig.id_grupo == group_id,
            DiarioConfig.inativo == False,
        )
        .first()
    )
    if not config:
        raise HTTPException(
            status_code=404,
            detail="Configuração daily não encontrada para este grupo",
        )

    # Check if user has a daily entry for today
    today = now_in_app_timezone().date()

    atribuicao = (
        db.query(Atribuicao)
        .filter(
            Atribuicao.id_grupo == group_id,
            Atribuicao.id_usuario == current_user_id,
            Atribuicao.inativo == False,
        )
        .first()
    )

    has_registro_hoje = False
    if atribuicao:
        registro_hoje = (
            db.query(DiarioItem)
            .filter(
                DiarioItem.id_diario_config == config.id,
                DiarioItem.id_atribuicao_usuario == atribuicao.id,
                DiarioItem.data_diario == today,
                DiarioItem.inativo == False,
            )
            .first()
        )
        if registro_hoje:
            has_registro_hoje = True

    return {
        "id": config.id,
        "hasRegistroHoje": has_registro_hoje,
        "grupo": config.grupo,
    }
