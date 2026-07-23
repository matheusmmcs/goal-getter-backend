from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.agendamento import Agendamento
from math import ceil

def list_all(db: Session, page: int, size: int):
    query = db.query(Agendamento).filter(Agendamento.inativo == False)
    total = query.count()
    items = query.offset(page * size).limit(size).all()
    return {
        "items": items,
        "count": len(items),
        "page": page,
        "size": size,
        "totalPages": ceil(total / size) if size > 0 else 0
    }

def get_by_id(db: Session, id: str):
    item = db.query(Agendamento).filter(Agendamento.id == id, Agendamento.inativo == False).first()
    if not item:
        raise HTTPException(status_code=404, detail="Agendamento not found")
    return item

def create(db: Session, data: dict):
    item = Agendamento(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def update(db: Session, id: str, data: dict):
    item = get_by_id(db, id)
    for k, v in data.items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item

def deactivate(db: Session, id: str):
    item = get_by_id(db, id)
    item.inativo = True
    db.commit()
    return {"success": True, "message": "Deactivated"}
