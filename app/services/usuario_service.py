from sqlalchemy.orm import Session, selectinload
from fastapi import HTTPException
from app.models.usuario import Usuario
from app.models.atribuicao import Atribuicao
from app.models.perfil import Perfil
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate
from app.core.security import get_password_hash
import math

def list_active(db: Session, page: int, size: int):
    query = db.query(Usuario).filter(Usuario.inativo == False)
    total = query.count()
    items = query.offset(page * size).limit(size).all()
    return {
        "items": items,
        "count": len(items),
        "page": page,
        "size": size,
        "totalPages": math.ceil(total / size) if size > 0 else 0
    }

def get_by_id(db: Session, user_id: str) -> Usuario:
    user = db.query(Usuario).options(
        selectinload(Usuario.perfis),
        selectinload(Usuario.atribuicoes)
    ).filter(Usuario.id == user_id, Usuario.inativo == False).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return user

def create(db: Session, data: UsuarioCreate) -> Usuario:
    user_data = data.model_dump()
    if "senha" in user_data and user_data["senha"]:
        user_data["senha"] = get_password_hash(user_data["senha"])
    new_user = Usuario(**user_data)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def update(db: Session, user_id: str, data: UsuarioUpdate) -> Usuario:
    user = get_by_id(db, user_id)
    update_data = data.model_dump(exclude_unset=True)
    if "senha" in update_data and update_data["senha"]:
        update_data["senha"] = get_password_hash(update_data["senha"])
    for key, value in update_data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user

def deactivate(db: Session, user_id: str):
    user = get_by_id(db, user_id)
    user.inativo = True
    db.commit()
    db.refresh(user)
    return user

def get_atribuicoes(db: Session, user_id: str):
    return db.query(Atribuicao).options(
        selectinload(Atribuicao.grupo),
        selectinload(Atribuicao.nivel)
    ).filter(Atribuicao.id_usuario == user_id, Atribuicao.inativo == False).all()

def get_perfis(db: Session, user_id: str):
    return db.query(Perfil).options(
        selectinload(Perfil.unidade),
        selectinload(Perfil.nivel)
    ).filter(Perfil.id_usuario == user_id, Perfil.inativo == False).all()
