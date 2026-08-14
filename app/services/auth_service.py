from sqlalchemy.orm import Session, selectinload
from fastapi import HTTPException, status

from app.core.security import verify_password, create_access_token, get_password_hash
from app.core.timezone import now_in_app_timezone
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequest
from app.schemas.usuario import UsuarioRegister


import re

def authenticate_user(db: Session, usuario: str, senha: str) -> Usuario | None:
    """Authenticate user by username or email and password."""
    clean_login = usuario.strip()
    user = db.query(Usuario).filter(
        (Usuario.usuario.ilike(clean_login)) | (Usuario.email.ilike(clean_login))
    ).first()
    if not user:
        return None
    if not verify_password(senha, user.senha):
        return None
    if not user.is_autorizado or user.inativo:
        return None
    return user


def register_user(db: Session, data: UsuarioRegister) -> Usuario:
    """Self-register a new user with nickname, email and cpf validations."""
    nome_clean = data.nome.strip()
    if not nome_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome é obrigatório"
        )

    usuario_clean = data.usuario.strip()
    if not usuario_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome de usuário é obrigatório"
        )

    existing_user = db.query(Usuario).filter(Usuario.usuario.ilike(usuario_clean)).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome de usuário já está em uso"
        )

    email_clean = data.email.strip() if data.email else ""
    if not email_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="E-mail é obrigatório"
        )

    existing_email = db.query(Usuario).filter(Usuario.email.ilike(email_clean)).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="E-mail já está cadastrado"
        )

    nickname_clean = data.nickname.strip() if data.nickname and data.nickname.strip() else usuario_clean
    if nickname_clean:
        existing_nickname = db.query(Usuario).filter(Usuario.nickname.ilike(nickname_clean)).first()
        if existing_nickname:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nickname já está em uso"
            )

    cpf_digits = None
    if data.cpf and data.cpf.strip():
        cpf_digits = re.sub(r'\D', '', data.cpf.strip())
        if cpf_digits:
            existing_cpf = db.query(Usuario).filter(Usuario.cpf == cpf_digits).first()
            if existing_cpf:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="CPF já está cadastrado"
                )

    if len(data.senha) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha deve ter no mínimo 8 caracteres"
        )

    now = now_in_app_timezone()
    new_user = Usuario(
        usuario=usuario_clean,
        nome=nome_clean,
        nickname=nickname_clean,
        email=email_clean,
        cpf=cpf_digits,
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
            "nickname": full_user.nickname,
            "email": full_user.email,
            "cpf": full_user.cpf,
            "is_admin": full_user.is_admin,
            "organizacoes": orgs_list,
            "perfis": [],
        },
    }


def check_username_availability(db: Session, username: str) -> dict:
    """Verifica se o nome de usuário está disponível e sugere sufixo numérico (ex: 2) caso já exista."""
    clean = username.strip()
    if not clean:
        return {"available": False, "suggested": ""}

    exists = db.query(Usuario).filter(Usuario.usuario.ilike(clean)).first() is not None
    suggested = clean
    if exists:
        counter = 2
        while db.query(Usuario).filter(Usuario.usuario.ilike(f"{clean}{counter}")).first() is not None:
            counter += 1
        suggested = f"{clean}{counter}"

    return {
        "available": not exists,
        "suggested": suggested
    }


