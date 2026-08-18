from typing import Annotated
from uuid import UUID
from fastapi import Depends, HTTPException, status, Header, Query
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.models.usuario import Usuario
from app.models.organizacao import Organizacao
from app.models.usuario_organizacao import UsuarioOrganizacao
from app.models.enums import PapelOrganizacaoEnum

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='api/auth/login')

def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)]
) -> Usuario:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="auth.invalid_credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_raw: str | None = payload.get("sub")
        if user_id_raw is None:
            raise credentials_exception
        user_id = UUID(str(user_id_raw))
    except (JWTError, ValueError, TypeError):
        raise credentials_exception
        
    user = db.query(Usuario).filter(Usuario.id == user_id).first()

    if user is None:
        raise credentials_exception
    if not user.ativo or user.inativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="auth.user_inactive")
    if not user.is_autorizado:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="auth.user_unauthorized")
        
    return user

def require_admin(current_user: Annotated[Usuario, Depends(get_current_user)]) -> Usuario:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="auth.admin_required")
    return current_user

def require_active_organization(
    current_user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    x_organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
    id_organizacao: Annotated[UUID | None, Query()] = None,
) -> Organizacao:
    target_raw_id = id_organizacao or x_organization_id
    if not target_raw_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="organization.organization_required"
        )
    try:
        org_id = UUID(str(target_raw_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="organization.invalid_id_format"
        )

    org = db.query(Organizacao).filter(
        Organizacao.id == org_id,
        Organizacao.inativo == False
    ).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="organization.not_found_or_inactive"
        )

    if not current_user.is_admin:
        vinculo = db.query(UsuarioOrganizacao).filter(
            UsuarioOrganizacao.id_organizacao == org_id,
            UsuarioOrganizacao.id_usuario == current_user.id,
            UsuarioOrganizacao.inativo == False
        ).first()
        if not vinculo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="authorization.organization_member_required"
            )

    return org

def get_current_organization_id(
    current_user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    x_organization_id: Annotated[str | None, Header(alias="X-Organization-Id")] = None,
    id_organizacao: Annotated[UUID | None, Query()] = None,
) -> UUID | None:
    raw_id = id_organizacao or x_organization_id
    if not raw_id:
        return None
    try:
        org_id = UUID(str(raw_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="organization.invalid_id_format"
        )

    org = db.query(Organizacao).filter(
        Organizacao.id == org_id,
        Organizacao.inativo == False
    ).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="organization.not_found_or_inactive"
        )

    if not current_user.is_admin:
        vinculo = db.query(UsuarioOrganizacao).filter(
            UsuarioOrganizacao.id_organizacao == org_id,
            UsuarioOrganizacao.id_usuario == current_user.id,
            UsuarioOrganizacao.inativo == False
        ).first()
        if not vinculo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="authorization.organization_member_required"
            )

    return org_id

def require_org_gestor(
    org_id: str | UUID,
    current_user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Usuario:
    if current_user.is_admin:
        return current_user

    vinculo = db.query(UsuarioOrganizacao).filter(
        UsuarioOrganizacao.id_organizacao == org_id,
        UsuarioOrganizacao.id_usuario == current_user.id,
        UsuarioOrganizacao.inativo == False,
        UsuarioOrganizacao.papel_organizacao == PapelOrganizacaoEnum.GESTOR
    ).first()

    if not vinculo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="authorization.organization_manager_required")

    return current_user

def require_org_member(
    org_id: str | UUID,
    current_user: Annotated[Usuario, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> Usuario:
    if current_user.is_admin:
        return current_user

    vinculo = db.query(UsuarioOrganizacao).filter(
        UsuarioOrganizacao.id_organizacao == org_id,
        UsuarioOrganizacao.id_usuario == current_user.id,
        UsuarioOrganizacao.inativo == False,
    ).first()

    if not vinculo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="authorization.organization_member_required")

    return current_user



