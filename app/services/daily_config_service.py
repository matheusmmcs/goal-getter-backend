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
    """Get config summary for a group, auto-creating a default config if it doesn't exist."""
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
        # Check if group exists
        grupo = db.query(GrupoTrabalho).filter(GrupoTrabalho.id == group_id, GrupoTrabalho.inativo == False).first()
        if not grupo:
            raise HTTPException(
                status_code=404,
                detail="Grupo não encontrado",
            )
        
        # Auto-create default daily config
        config = DiarioConfig(
            id_grupo=group_id,
            periodo_addnota_inicio="08:00",
            periodo_addnota_fim="18:00",
            is_retroativo=True,
            is_permite_atrasado=True,
            is_publico_para_grupo=True,
        )
        db.add(config)
        db.commit()
        db.refresh(config)
        # Reload with relationship
        config = (
            db.query(DiarioConfig)
            .options(joinedload(DiarioConfig.grupo))
            .filter(DiarioConfig.id == config.id)
            .first()
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


def create_config(db: Session, group_id: UUID, data):
    """Create a new daily config for a group."""
    grupo = db.query(GrupoTrabalho).filter(GrupoTrabalho.id == group_id, GrupoTrabalho.inativo == False).first()
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")

    existing = db.query(DiarioConfig).filter(
        DiarioConfig.id_grupo == group_id,
        DiarioConfig.inativo == False,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Este grupo já possui uma configuração de diário ativa")

    new_config = DiarioConfig(
        id_grupo=group_id,
        periodo_addnota_inicio=data.periodo_addnota_inicio,
        periodo_addnota_fim=data.periodo_addnota_fim,
        is_retroativo=data.is_retroativo,
        is_permite_atrasado=data.is_permite_atrasado,
        is_publico_para_grupo=data.is_publico_para_grupo,
        canal_chatmessage=data.canal_chatmessage,
    )
    db.add(new_config)
    db.commit()
    db.refresh(new_config)
    return get_config(db, new_config.id)


def update_config(db: Session, config_id: UUID, data):
    """Update an existing daily config."""
    config = db.query(DiarioConfig).filter(DiarioConfig.id == config_id, DiarioConfig.inativo == False).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuração daily não encontrada")

    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(config, key, value)

    config.updated_at = now_in_app_timezone()
    db.commit()
    db.refresh(config)
    return get_config(db, config.id)

