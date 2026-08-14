from uuid import UUID
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.unidade import Unidade
import math


def list_all(db: Session, page: int, size: int, id_organizacao: Optional[UUID] = None):
    query = db.query(Unidade).filter(Unidade.inativo == False)
    if id_organizacao:
        query = query.filter(Unidade.id_organizacao == id_organizacao)
    total = query.count()
    items = query.offset(page * size).limit(size).all()
    return {
        "items": items,
        "count": len(items),
        "total": total,
        "page": page,
        "size": size,
        "totalPages": math.ceil(total / size) if size > 0 else 0
    }


def get_by_id(db: Session, id: UUID) -> Unidade:
    unidade = db.query(Unidade).filter(Unidade.id == id, Unidade.inativo == False).first()
    if not unidade:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")
    return unidade

def create(db: Session, data, id_organizacao: Optional[UUID] = None) -> Unidade:
    unidade_data = data.model_dump()
    if id_organizacao and not unidade_data.get("id_organizacao"):
        unidade_data["id_organizacao"] = id_organizacao
    nova_unidade = Unidade(**unidade_data)
    db.add(nova_unidade)
    db.commit()
    db.refresh(nova_unidade)
    return nova_unidade

def update(db: Session, id: UUID, data) -> Unidade:
    unidade = get_by_id(db, id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(unidade, key, value)
    db.commit()
    db.refresh(unidade)
    return unidade

def deactivate(db: Session, id: UUID):
    unidade = get_by_id(db, id)
    unidade.inativo = True
    db.commit()
    db.refresh(unidade)
    return unidade
