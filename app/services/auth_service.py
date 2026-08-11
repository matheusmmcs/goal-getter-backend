from sqlalchemy.orm import Session, selectinload
from fastapi import HTTPException, status

from app.core.security import verify_password, create_access_token, get_password_hash
from app.core.timezone import now_in_app_timezone
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequest
from app.schemas.usuario import UsuarioRegister


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


def register_user(db: Session, data: UsuarioRegister) -> Usuario:
    """Self-register a new user."""
    existing_user = db.query(Usuario).filter(Usuario.usuario.ilike(data.usuario.strip())).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome de usuário já está em uso"
        )
    
    if data.email and data.email.strip():
        existing_email = db.query(Usuario).filter(Usuario.email.ilike(data.email.strip())).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="E-mail já está cadastrado"
            )

    now = now_in_app_timezone()
    new_user = Usuario(
        usuario=data.usuario.strip(),
        nome=data.nome.strip(),
        email=data.email.strip() if data.email else None,
        cpf=data.cpf.strip() if data.cpf else None,
        senha=get_password_hash(data.senha),
        is_admin=False,
        is_autorizado=True,
        inativo=False,
        data_autorizacao=now
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


def login(db: Session, credentials: LoginRequest) -> dict:
    """Authenticate and return token + user data for the frontend."""
    user = authenticate_user(db, credentials.usuario, credentials.senha)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reload with perfis, atribuicoes and organizacoes_vinculos for the response
    from app.models.usuario_organizacao import UsuarioOrganizacao
    from app.models.organizacao import Organizacao
    
    full_user = (
        db.query(Usuario)
        .options(
            selectinload(Usuario.perfis),
            selectinload(Usuario.atribuicoes),
            selectinload(Usuario.organizacoes_vinculos).selectinload(UsuarioOrganizacao.organizacao)
        )
        .filter(Usuario.id == user.id)
        .first()
    )
    if not full_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
        )

    # Coletar organizacoes ativas do usuario
    orgs_list = []
    if full_user.is_admin:
        all_orgs = db.query(Organizacao).filter(Organizacao.inativo == False).all()
        for org in all_orgs:
            # Verifica se possui papel especifico, senão assume GESTOR por ser admin
            v = next((v for v in full_user.organizacoes_vinculos if v.id_organizacao == org.id and not v.inativo), None)
            orgs_list.append({
                "id": str(org.id),
                "nome": org.nome,
                "sigla": org.sigla,
                "papel_organizacao": v.papel_organizacao if v else "GESTOR"
            })
    else:
        for v in full_user.organizacoes_vinculos:
            if v.organizacao and not v.inativo and not v.organizacao.inativo:
                orgs_list.append({
                    "id": str(v.organizacao.id),
                    "nome": v.organizacao.nome,
                    "sigla": v.organizacao.sigla,
                    "papel_organizacao": v.papel_organizacao
                })

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
            "organizacoes": orgs_list,
            "perfis": [],
        },
    }

