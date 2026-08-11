from uuid import UUID
from sqlalchemy.orm import Session, selectinload
from fastapi import HTTPException
from app.models.usuario import Usuario
from app.models.atribuicao import Atribuicao
from app.models.perfil import Perfil
from app.models.grupo import GrupoTrabalho
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate
from app.core.security import get_password_hash
import math

def list_usuarios(
    db: Session,
    page: int,
    size: int,
    nome: str | None = None,
    inativo: bool | str | None = None,
    include_inactive: bool = True
):
    query = db.query(Usuario)

    inativo_bool = None
    if isinstance(inativo, bool):
        inativo_bool = inativo
    elif isinstance(inativo, str):
        if inativo.lower() in ("false", "0", "active", "ativo"):
            inativo_bool = False
        elif inativo.lower() in ("true", "1", "inactive", "inativo"):
            inativo_bool = True
        elif inativo.lower() in ("all", "todos", "none", ""):
            inativo_bool = None

    if inativo_bool is not None:
        query = query.filter(Usuario.inativo == inativo_bool)
    elif not include_inactive:
        query = query.filter(Usuario.inativo == False)

    if nome and nome.strip():
        search_term = f"%{nome.strip()}%"
        query = query.filter(
            (Usuario.nome.ilike(search_term)) | (Usuario.usuario.ilike(search_term))
        )

    total = query.count()
    items = query.order_by(Usuario.created_at.desc()).offset(page * size).limit(size).all()
    return {
        "items": items,
        "count": len(items),
        "page": page,
        "size": size,
        "totalPages": math.ceil(total / size) if size > 0 else 0
    }

def list_active(db: Session, page: int, size: int):
    return list_usuarios(db, page, size, include_inactive=False)

def get_by_id(db: Session, user_id: UUID, include_inactive: bool = True) -> Usuario:
    query = db.query(Usuario).options(
        selectinload(Usuario.perfis),
        selectinload(Usuario.atribuicoes)
    ).filter(Usuario.id == user_id)
    if not include_inactive:
        query = query.filter(Usuario.inativo == False)
    user = query.first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return user

from app.core.timezone import now_in_app_timezone

def create(db: Session, data: UsuarioCreate) -> Usuario:
    user_data = data.model_dump()
    if "senha" in user_data and user_data["senha"]:
        user_data["senha"] = get_password_hash(user_data["senha"])
    
    now = now_in_app_timezone()
    if user_data.get("is_autorizado"):
        user_data["data_autorizacao"] = now
    if user_data.get("inativo"):
        user_data["data_inativacao"] = now

    new_user = Usuario(**user_data)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def update(db: Session, user_id: UUID, data: UsuarioUpdate) -> Usuario:
    user = get_by_id(db, user_id, include_inactive=True)
    update_data = data.model_dump(exclude_unset=True)
    if "senha" in update_data and update_data["senha"]:
        update_data["senha"] = get_password_hash(update_data["senha"])
    
    now = now_in_app_timezone()
    update_data["updated_at"] = now

    if "is_autorizado" in update_data:
        if update_data["is_autorizado"] and not user.is_autorizado:
            update_data["data_autorizacao"] = now
        elif not update_data["is_autorizado"]:
            update_data["data_autorizacao"] = None

    if "inativo" in update_data:
        if update_data["inativo"] and not user.inativo:
            update_data["data_inativacao"] = now
        elif not update_data["inativo"]:
            update_data["data_inativacao"] = None

    for key, value in update_data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user

def deactivate(db: Session, user_id: UUID):
    user = get_by_id(db, user_id, include_inactive=True)
    now = now_in_app_timezone()
    user.inativo = True
    user.data_inativacao = now
    user.updated_at = now
    db.commit()
    db.refresh(user)
    return user

def reactivate(db: Session, user_id: UUID):
    user = get_by_id(db, user_id, include_inactive=True)
    now = now_in_app_timezone()
    user.inativo = False
    user.data_inativacao = None
    user.updated_at = now
    db.commit()
    db.refresh(user)
    return user

def get_atribuicoes(db: Session, user_id: UUID):
    return db.query(Atribuicao).options(
        selectinload(Atribuicao.grupo).selectinload(GrupoTrabalho.unidade),
        selectinload(Atribuicao.nivel)
    ).filter(Atribuicao.id_usuario == user_id, Atribuicao.inativo == False).all()

def get_perfis(db: Session, user_id: UUID):
    return db.query(Perfil).options(
        selectinload(Perfil.unidade),
        selectinload(Perfil.nivel)
    ).filter(Perfil.id_usuario == user_id, Perfil.inativo == False).all()
