from sqlalchemy.orm import Session, selectinload
from fastapi import HTTPException, status

from app.core.security import verify_password, create_access_token
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequest


def authenticate_user(db: Session, usuario: str, senha: str) -> Usuario | None:
    """Authenticate user by username and password."""
    user = db.query(Usuario).filter(Usuario.usuario.ilike(usuario)).first()
    if not user:
        return None
    if not verify_password(senha, user.senha):
        return None
    if not user.is_autorizado or user.inativo:
        return None
    return user


def login(db: Session, credentials: LoginRequest) -> dict:
    """Authenticate and return token + user data for the frontend."""
    user = authenticate_user(db, credentials.usuario, credentials.senha)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reload with perfis and atribuicoes for the response
    full_user = (
        db.query(Usuario)
        .options(
            selectinload(Usuario.perfis),
            selectinload(Usuario.atribuicoes),
        )
        .filter(Usuario.id == user.id)
        .first()
    )
    if not full_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
        )

    role = "admin" if full_user.is_admin else "user"
    access_token = create_access_token(
        data={"sub": str(full_user.id), "role": role}
    )

    return {
        "token": access_token,
        "user": {
            "id": full_user.id,
            "nome": full_user.nome,
            "usuario": full_user.usuario,
            "email": full_user.email,
            "cpf": full_user.cpf,
            "is_admin": full_user.is_admin,
            "perfis": [],
        },
    }
