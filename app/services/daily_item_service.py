import calendar
import logging
from datetime import date
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import settings
from app.core.timezone import now_in_app_timezone
from app.models.atribuicao import Atribuicao
from app.models.diario_config import DiarioConfig
from app.models.diario_item import DiarioItem
from app.models.diario_item_anotacao import DiarioItemAnotacao
from app.models.enums import TipoDiarioItemAnotacaoEnum
from app.schemas.daily import DiarioItemCreate

logger = logging.getLogger(__name__)


def _build_date(year: int, month: int, day: int) -> date:
    """Build a date object from year/month/day path parameters."""
    try:
        return date(year, month, day)
    except ValueError:
        raise HTTPException(status_code=400, detail="Data inválida")


def get_items_by_month(db: Session, config_id: UUID, year: int, month: int):
    _, last_day = calendar.monthrange(year, month)
    start_date = date(year, month, 1)
    end_date = date(year, month, last_day)

    items = (
        db.query(DiarioItem)
        .options(
            selectinload(DiarioItem.notas),
            joinedload(DiarioItem.atribuicao_usuario).joinedload(Atribuicao.usuario),
        )
        .filter(
            DiarioItem.id_diario_config == config_id,
            DiarioItem.data_diario >= start_date,
            DiarioItem.data_diario <= end_date,
            DiarioItem.inativo == False,
        )
        .all()
    )
    return items


def get_items_by_day(db: Session, config_id: UUID, year: int, month: int, day: int):
    target_date = _build_date(year, month, day)

    items = (
        db.query(DiarioItem)
        .options(
            selectinload(DiarioItem.notas),
            joinedload(DiarioItem.atribuicao_usuario).joinedload(Atribuicao.usuario),
        )
        .filter(
            DiarioItem.id_diario_config == config_id,
            DiarioItem.data_diario == target_date,
            DiarioItem.inativo == False,
        )
        .all()
    )
    return items


def get_item_by_id(
    db: Session, config_id: UUID, year: int, month: int, day: int, item_id: UUID
):
    item = (
        db.query(DiarioItem)
        .options(
            selectinload(DiarioItem.notas),
            joinedload(DiarioItem.atribuicao_usuario).joinedload(Atribuicao.usuario),
        )
        .filter(
            DiarioItem.id == item_id,
            DiarioItem.id_diario_config == config_id,
            DiarioItem.inativo == False,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Registro daily não encontrado")
    return item


def _send_to_redmine_sync(tarefa_id: int, nota_text: str):
    """Send a note to Redmine issue (synchronous, best-effort)."""
    if not settings.REDMINE_ENABLED or not tarefa_id:
        return
    url = f"{settings.REDMINE_URL}/issues/{tarefa_id}.json"
    headers = {"X-Redmine-API-Key": settings.REDMINE_API_KEY}
    payload = {"issue": {"notes": nota_text}}
    try:
        with httpx.Client(timeout=10) as client:
            client.put(url, json=payload, headers=headers)
        logger.info(f"Nota enviada ao Redmine issue #{tarefa_id}")
    except Exception as e:
        logger.warning(f"Falha ao enviar nota ao Redmine issue #{tarefa_id}: {e}")


def _send_chat_webhook_sync(message: str):
    """Send impediment notification to Chat (synchronous, best-effort)."""
    if not settings.CHAT_ENABLED or not settings.CHAT_WEBHOOK_URL:
        return
    try:
        with httpx.Client(timeout=10) as client:
            client.post(settings.CHAT_WEBHOOK_URL, json={"text": message})
        logger.info("Notificação de impedimento enviada ao Chat")
    except Exception as e:
        logger.warning(f"Falha ao enviar notificação ao Chat: {e}")


def create_item(
    db: Session,
    config_id: UUID,
    year: int,
    month: int,
    day: int,
    data: DiarioItemCreate,
    current_user,
) -> DiarioItem:
    # 1. Find config
    config = db.query(DiarioConfig).filter(DiarioConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Configuração daily não encontrada")

    # 2. Find user's atribuição in the config's group
    atribuicao = (
        db.query(Atribuicao)
        .filter(
            Atribuicao.id_grupo == config.id_grupo,
            Atribuicao.id_usuario == current_user.id,
            Atribuicao.inativo == False,
        )
        .first()
    )
    if not atribuicao:
        raise HTTPException(
            status_code=403, detail="Usuário não pertence a este grupo"
        )

    # 3. Check uniqueness: 1 item per day per config per user
    target_date = _build_date(year, month, day)
    existing = (
        db.query(DiarioItem)
        .filter(
            DiarioItem.id_diario_config == config_id,
            DiarioItem.id_atribuicao_usuario == atribuicao.id,
            DiarioItem.data_diario == target_date,
            DiarioItem.inativo == False,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Já existe um registro daily para este dia",
        )

    # 4. Create item
    new_item = DiarioItem(
        id_diario_config=config_id,
        id_atribuicao_usuario=atribuicao.id,
        data_diario=target_date,
        is_atrasado=data.is_atrasado,
    )
    db.add(new_item)
    db.flush()

    # 5. Create annotations by type
    has_impediment = False
    impediment_texts = []

    for tipo_key, notas_list in data.notas.items():
        try:
            tipo_enum = TipoDiarioItemAnotacaoEnum(tipo_key)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Tipo de anotação inválido: {tipo_key}. Use: TODAY, YESTERDAY, IMPEDIMENT",
            )

        for nota in notas_list:
            anotacao = DiarioItemAnotacao(
                id_diario_item=new_item.id,
                tipo=tipo_enum,
                descricao=nota.descricao,
                id_tarefa=nota.id_tarefa,
                petrvs_entrega_id=nota.petrvs_entrega_id,
                petrvs_entrega_desc=nota.petrvs_entrega_desc,
            )
            db.add(anotacao)

            # Redmine integration
            if nota.id_tarefa and nota.descricao:
                _send_to_redmine_sync(nota.id_tarefa, nota.descricao)

            if tipo_enum == TipoDiarioItemAnotacaoEnum.IMPEDIMENT:
                has_impediment = True
                impediment_texts.append(nota.descricao or "")

    db.commit()
    db.refresh(new_item)

    # 6. Chat webhook for impediments
    if has_impediment:
        user_name = getattr(current_user, "nome", str(current_user.id))
        msg = f"⚠️ Impedimento reportado por {user_name}: {'; '.join(impediment_texts)}"
        _send_chat_webhook_sync(msg)

    return new_item


def update_item(
    db: Session,
    config_id: UUID,
    year: int,
    month: int,
    day: int,
    item_id: UUID,
    data: DiarioItemCreate,
) -> DiarioItem:
    item = (
        db.query(DiarioItem)
        .filter(
            DiarioItem.id == item_id,
            DiarioItem.id_diario_config == config_id,
            DiarioItem.inativo == False,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Registro daily não encontrado")

    # Update is_atrasado
    item.is_atrasado = data.is_atrasado

    # Get existing active notes
    existing_notas = (
        db.query(DiarioItemAnotacao)
        .filter(
            DiarioItemAnotacao.id_diario_item == item_id,
            DiarioItemAnotacao.inativo == False,
        )
        .all()
    )

    # Deactivate all existing notes
    for nota in existing_notas:
        nota.inativo = True

    # Create new notes from submitted data
    for tipo_key, notas_list in data.notas.items():
        try:
            tipo_enum = TipoDiarioItemAnotacaoEnum(tipo_key)
        except ValueError:
            continue

        for nota in notas_list:
            new_nota = DiarioItemAnotacao(
                id_diario_item=item.id,
                tipo=tipo_enum,
                descricao=nota.descricao,
                id_tarefa=nota.id_tarefa,
                petrvs_entrega_id=nota.petrvs_entrega_id,
                petrvs_entrega_desc=nota.petrvs_entrega_desc,
            )
            db.add(new_nota)

    db.commit()
    db.refresh(item)
    return item


def get_report(
    db: Session, config_id: UUID, date_start: str, date_end: str, group_id: UUID
) -> dict:
    """Generate report grouped by user name for a date range."""
    try:
        start = date.fromisoformat(date_start)
        end = date.fromisoformat(date_end)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Formato de data inválido. Use YYYY-MM-DD.",
        )

    items = (
        db.query(DiarioItem)
        .join(Atribuicao, DiarioItem.id_atribuicao_usuario == Atribuicao.id)
        .filter(
            DiarioItem.id_diario_config == config_id,
            Atribuicao.id_grupo == group_id,
            DiarioItem.data_diario >= start,
            DiarioItem.data_diario <= end,
            DiarioItem.inativo == False,
        )
        .options(
            selectinload(DiarioItem.notas),
            joinedload(DiarioItem.atribuicao_usuario).joinedload(Atribuicao.usuario),
        )
        .all()
    )

    report: dict[str, list] = {}
    for item in items:
        user_name = str(item.id_atribuicao_usuario)
        if (
            item.atribuicao_usuario
            and hasattr(item.atribuicao_usuario, "usuario")
            and item.atribuicao_usuario.usuario
        ):
            user_name = item.atribuicao_usuario.usuario.nome

        if user_name not in report:
            report[user_name] = []

        active_notas = [n for n in item.notas if not n.inativo]
        report[user_name].append(
            {
                "data_diario": item.data_diario.isoformat(),
                "notas": active_notas,
            }
        )

    return report
