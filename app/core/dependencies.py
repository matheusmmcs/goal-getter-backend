from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.models.usuario import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='api/auth/login')

def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)]
) -> Usuario:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(Usuario).filter(Usuario.id == str(user_id)).first()
    if user is None:
        raise credentials_exception
    if not user.ativo or user.inativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inativo")
    if not user.is_autorizado:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário não autorizado")
        
    return user

def require_admin(current_user: Annotated[Usuario, Depends(get_current_user)]) -> Usuario:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a administradores")
    return current_user

def get_current_organization_id(
    x_organization_id: Annotated[str | None, Depends(lambda: None)] = None,
) -> str | None:
    return x_organization_id

def require_org_gestor(
    org_id: str,
    current_user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Usuario:
    if current_user.is_admin:
        return current_user

    from app.models.usuario_organizacao import UsuarioOrganizacao
    from app.models.enums import PapelOrganizacaoEnum

    vinculo = db.query(UsuarioOrganizacao).filter(
        UsuarioOrganizacao.id_organizacao == org_id,
        UsuarioOrganizacao.id_usuario == current_user.id,
        UsuarioOrganizacao.inativo == False,
        UsuarioOrganizacao.papel_organizacao == PapelOrganizacaoEnum.GESTOR
    ).first()

    if not vinculo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso permitido apenas a Gestores da Organização ou Administradores")

    return current_user

