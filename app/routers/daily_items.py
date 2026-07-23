from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.daily import DiarioItemCreate
from app.services import daily_item_service

router = APIRouter()


@router.get("/{config_id}/items/{year}/{month}")
def get_items_month(
    config_id: UUID,
    year: int,
    month: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = daily_item_service.get_items_by_month(db, config_id, year, month)
    return {"success": True, "message": "Registros do mês recuperados", "data": data}


@router.get("/{config_id}/items/{year}/{month}/{day}")
def get_items_day(
    config_id: UUID,
    year: int,
    month: int,
    day: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = daily_item_service.get_items_by_day(db, config_id, year, month, day)
    return {"success": True, "message": "Registros do dia recuperados", "data": data}


@router.get("/{config_id}/items/{year}/{month}/{day}/{item_id}")
def get_item(
    config_id: UUID,
    year: int,
    month: int,
    day: int,
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = daily_item_service.get_item_by_id(db, config_id, year, month, day, item_id)
    return {"success": True, "message": "Registro recuperado", "data": data}


@router.post("/{config_id}/items/{year}/{month}/{day}")
def create_item(
    config_id: UUID,
    year: int,
    month: int,
    day: int,
    payload: DiarioItemCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = daily_item_service.create_item(
        db, config_id, year, month, day, payload, current_user
    )
    return {"success": True, "message": "Registro daily criado", "data": data}


@router.put("/{config_id}/items/{year}/{month}/{day}/{item_id}")
def update_item(
    config_id: UUID,
    year: int,
    month: int,
    day: int,
    item_id: UUID,
    payload: DiarioItemCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = daily_item_service.update_item(
        db, config_id, year, month, day, item_id, payload
    )
    return {"success": True, "message": "Registro daily atualizado", "data": data}


@router.get("/{config_id}/relatorio")
def get_report(
    config_id: UUID,
    inicio: str = Query(..., description="Data início (YYYY-MM-DD)"),
    fim: str = Query(..., description="Data fim (YYYY-MM-DD)"),
    grupo: UUID = Query(..., description="ID do grupo"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = daily_item_service.get_report(db, config_id, inicio, fim, grupo)
    return {"success": True, "message": "Relatório gerado", "data": data}
