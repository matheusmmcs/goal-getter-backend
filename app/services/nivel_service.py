from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.nivel import Nivel
import math

def list_all(db: Session, page: int, size: int):
    query = db.query(Nivel).filter(Nivel.inativo == False)
    total = query.count()
    items = query.offset(page * size).limit(size).all()
    return {
        "items": items,
        "count": len(items),
        "page": page,
        "size": size,
        "totalPages": math.ceil(total / size) if size > 0 else 0
    }

def get_by_id(db: Session, id: str) -> Nivel:
    nivel = db.query(Nivel).filter(Nivel.id == id, Nivel.inativo == False).first()
    if not nivel:
        raise HTTPException(status_code=404, detail="Nível não encontrado")
    return nivel

def create(db: Session, data) -> Nivel:
    novo_nivel = Nivel(**data.model_dump())
    db.add(novo_nivel)
    db.commit()
    db.refresh(novo_nivel)
    return novo_nivel

def update(db: Session, id: str, data) -> Nivel:
    nivel = get_by_id(db, id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(nivel, key, value)
    db.commit()
    db.refresh(nivel)
    return nivel

def deactivate(db: Session, id: str):
    nivel = get_by_id(db, id)
    nivel.inativo = True
    db.commit()
    db.refresh(nivel)
    return nivel
