from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.unidade import Unidade
import math

def list_all(db: Session, page: int, size: int):
    query = db.query(Unidade).filter(Unidade.inativo == False)
    total = query.count()
    items = query.offset(page * size).limit(size).all()
    return {
        "items": items,
        "count": len(items),
        "page": page,
        "size": size,
        "totalPages": math.ceil(total / size) if size > 0 else 0
    }

def get_by_id(db: Session, id: UUID) -> Unidade:
    unidade = db.query(Unidade).filter(Unidade.id == id, Unidade.inativo == False).first()
    if not unidade:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")
    return unidade

def create(db: Session, data) -> Unidade:
    nova_unidade = Unidade(**data.model_dump())
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
