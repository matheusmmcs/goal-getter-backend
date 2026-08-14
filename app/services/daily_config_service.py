from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.timezone import now_in_app_timezone
from app.models.atribuicao import Atribuicao
from app.models.diario_config import DiarioConfig
from app.models.diario_item import DiarioItem
from app.models.enums import NivelCodigoEnum
from app.models.grupo import GrupoTrabalho


def format_group_data(grupo: GrupoTrabalho | None):
    if not grupo:
        return None
    atribuicoes = []
    usuarios_chefes = []
    for a in grupo.atribuicoes or []:
        if a.inativo:
            continue
        is_chefe = bool(a.nivel and a.nivel.valor == NivelCodigoEnum.GESTOR_GRUPO.value)
        if is_chefe and a.usuario:
            usuarios_chefes.append({
                "id": str(a.usuario.id),
                "nome": a.usuario.nome,
                "usuario": a.usuario.usuario,
                "email": a.usuario.email,
            })
        atribuicoes.append({
            "id": str(a.id),
            "id_usuario": str(a.id_usuario),
            "id_grupo": str(a.id_grupo),
            "id_nivel": str(a.id_nivel),
            "registrador": a.registrador,
            "inativo": a.inativo,
            "isLeader": is_chefe,
            "isChefe": is_chefe,
            "papel": NivelCodigoEnum.GESTOR_GRUPO.name if is_chefe else NivelCodigoEnum.PARTICIPANTE.name,
            "nivel": {
                "id": str(a.nivel.id) if a.nivel else str(a.id_nivel),
                "nome": a.nivel.nome if a.nivel else "",
                "valor": a.nivel.valor if a.nivel else None,
                "tipo": str(a.nivel.tipo) if a.nivel else "ATRIBUICAO",
            } if a.nivel else None,
            "usuario": {
                "id": str(a.usuario.id),
                "nome": a.usuario.nome,
                "usuario": a.usuario.usuario,
                "nickname": a.usuario.nickname,
                "email": a.usuario.email,
            } if a.usuario else None,
        })

    return {
        "id": str(grupo.id),
        "nome": grupo.nome,
        "id_unidade": str(grupo.id_unidade) if grupo.id_unidade else None,
        "id_organizacao": str(grupo.id_organizacao) if grupo.id_organizacao else None,
        "inativo": grupo.inativo,
        "unidade": {
            "id": str(grupo.unidade.id),
            "nome": grupo.unidade.nome,
            "sigla": grupo.unidade.sigla,
        } if grupo.unidade else None,
        "atribuicoes": atribuicoes,
        "usuarios_chefes": usuarios_chefes,
    }


def get_config(db: Session, config_id: UUID):
    """Get detailed daily config with group, group's unidade and atribuições."""
    config = (
        db.query(DiarioConfig)
        .options(
            joinedload(DiarioConfig.grupo).selectinload(GrupoTrabalho.unidade),
            joinedload(DiarioConfig.grupo)
            .selectinload(GrupoTrabalho.atribuicoes)
            .joinedload(Atribuicao.usuario),
            joinedload(DiarioConfig.grupo)
            .selectinload(GrupoTrabalho.atribuicoes)
            .joinedload(Atribuicao.nivel),
        )
        .filter(DiarioConfig.id == config_id, DiarioConfig.inativo == False)
        .first()
    )
    if not config:
        raise HTTPException(
            status_code=404, detail="Configuração daily não encontrada"
        )
    return {
        "id": config.id,
        "periodo_addnota_inicio": config.periodo_addnota_inicio,
        "periodo_addnota_fim": config.periodo_addnota_fim,
        "is_retroativo": config.is_retroativo,
        "is_permite_atrasado": config.is_permite_atrasado,
        "is_publico_para_grupo": config.is_publico_para_grupo,
        "canal_chatmessage": config.canal_chatmessage,
        "inativo": config.inativo,
        "grupo": format_group_data(config.grupo),
    }


def get_config_by_group(db: Session, group_id: UUID, current_user):
    """Get or auto-create daily config for a group."""
    from app.services.daily_permission_service import check_user_can_edit_config

    current_user_id = current_user.id if hasattr(current_user, 'id') else current_user

    # Check if group exists
    grupo = (
        db.query(GrupoTrabalho)
        .filter(GrupoTrabalho.id == group_id, GrupoTrabalho.inativo == False)
        .first()
    )
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")

    config = (
        db.query(DiarioConfig)
        .options(
            joinedload(DiarioConfig.grupo).selectinload(GrupoTrabalho.unidade),
            joinedload(DiarioConfig.grupo)
            .selectinload(GrupoTrabalho.atribuicoes)
            .joinedload(Atribuicao.usuario),
            joinedload(DiarioConfig.grupo)
            .selectinload(GrupoTrabalho.atribuicoes)
            .joinedload(Atribuicao.nivel),
        )
        .filter(DiarioConfig.id_grupo == group_id, DiarioConfig.inativo == False)
        .first()
    )

    # Fallback: tentar obter configuração herdada da Unidade do grupo
    if not config and grupo.id_unidade:
        config = (
            db.query(DiarioConfig)
            .filter(DiarioConfig.id_unidade == grupo.id_unidade, DiarioConfig.inativo == False)
            .first()
        )

    # Auto-create default config if none exists
    if not config:
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
            .options(
                joinedload(DiarioConfig.grupo).selectinload(GrupoTrabalho.unidade),
                joinedload(DiarioConfig.grupo)
                .selectinload(GrupoTrabalho.atribuicoes)
                .joinedload(Atribuicao.usuario),
                joinedload(DiarioConfig.grupo)
                .selectinload(GrupoTrabalho.atribuicoes)
                .joinedload(Atribuicao.nivel),
            )
            .filter(DiarioConfig.id == config.id)
            .first()
        )

    if not config:
        raise HTTPException(status_code=404, detail="Configuração daily não encontrada")

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

    can_edit = False
    if hasattr(current_user, 'id'):
        can_edit = check_user_can_edit_config(db, current_user, group_id)

    return {
        "id": config.id,
        "periodo_addnota_inicio": config.periodo_addnota_inicio,
        "periodo_addnota_fim": config.periodo_addnota_fim,
        "is_retroativo": config.is_retroativo,
        "is_permite_atrasado": config.is_permite_atrasado,
        "is_publico_para_grupo": config.is_publico_para_grupo,
        "canal_chatmessage": config.canal_chatmessage,
        "hasRegistroHoje": has_registro_hoje,
        "grupo": format_group_data(config.grupo),
        "canEditConfig": can_edit,
    }


def create_config(db: Session, group_id: UUID, data):
    """Create a new daily config for a group."""
    grupo = db.query(GrupoTrabalho).filter(GrupoTrabalho.id == group_id, GrupoTrabalho.inativo == False).first()
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")

    existing = db.query(DiarioConfig).filter(
        DiarioConfig.id_grupo == group_id, DiarioConfig.inativo == False
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Este grupo já possui uma configuração de diário")

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
