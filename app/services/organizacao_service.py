import math
from uuid import UUID
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status
from app.models.organizacao import Organizacao
from app.models.usuario_organizacao import UsuarioOrganizacao
from app.models.usuario import Usuario
from app.models.unidade import Unidade
from app.models.grupo import GrupoTrabalho
from app.models.perfil import Perfil
from app.models.atribuicao import Atribuicao
from app.models.enums import PapelOrganizacaoEnum
from app.schemas.organizacao import OrganizacaoCreate, OrganizacaoUpdate, VinculoUpdateSchema, UsuarioVinculoItem



def list_organizacoes_for_user(
    db: Session,
    current_user: Usuario,
    page: int = 0,
    size: int = 50,
    include_inativos: bool = False
):
    query = db.query(Organizacao)

    if not current_user.is_admin:
        org_ids = (
            db.query(UsuarioOrganizacao.id_organizacao)
            .filter(
                UsuarioOrganizacao.id_usuario == current_user.id,
                UsuarioOrganizacao.inativo == False
            )
            .all()
        )
        allowed_ids = [item[0] for item in org_ids]
        query = query.filter(Organizacao.id.in_(allowed_ids))

        # Se nao pediu inativos explicitamente, filtra inativo == False
        if not include_inativos:
            query = query.filter(Organizacao.inativo == False)
    else:
        # Admin: se nao pediu inativos explicitamente, filtra inativo == False
        if not include_inativos:
            query = query.filter(Organizacao.inativo == False)

    total = query.count()
    items_raw = query.order_by(Organizacao.nome.asc()).offset(page * size).limit(size).all()

    vinculos = (
        db.query(UsuarioOrganizacao)
        .filter(
            UsuarioOrganizacao.id_usuario == current_user.id,
            UsuarioOrganizacao.inativo == False
        )
        .all()
    )
    vinculos_map = {str(v.id_organizacao): v.papel_organizacao for v in vinculos}

    items = []
    for org in items_raw:
        papel = vinculos_map.get(str(org.id))
        if not papel and current_user.is_admin:
            papel = PapelOrganizacaoEnum.GESTOR

        items.append({
            "id": org.id,
            "nome": org.nome,
            "sigla": org.sigla,
            "descricao": org.descricao,
            "inativo": org.inativo,
            "created_at": org.created_at,
            "updated_at": org.updated_at,
            "papel_organizacao": papel.value if (papel is not None and hasattr(papel, "value")) else papel
        })

    return {
        "items": items,
        "count": len(items),
        "total": total,
        "page": page,
        "size": size,
        "totalPages": math.ceil(total / size) if size > 0 else 0
    }


def get_by_id(db: Session, id: UUID) -> Organizacao:
    org = db.query(Organizacao).filter(Organizacao.id == id).first()
    if not org:
        raise HTTPException(status_code=404, detail="organization.not_found")
    return org


def get_detail_by_id(db: Session, id: UUID):
    org = get_by_id(db, id)

    unidades_count = db.query(Unidade).filter(Unidade.id_organizacao == id, Unidade.inativo == False).count()
    grupos_count = db.query(GrupoTrabalho).filter(GrupoTrabalho.id_organizacao == id, GrupoTrabalho.inativo == False).count()


    vinculos = (
        db.query(UsuarioOrganizacao)
        .options(joinedload(UsuarioOrganizacao.usuario))
        .filter(UsuarioOrganizacao.id_organizacao == id, UsuarioOrganizacao.inativo == False)
        .all()
    )

    vinculos_response = []
    for v in vinculos:
        vinculos_response.append({
            "id": v.id,
            "id_usuario": v.id_usuario,
            "id_organizacao": v.id_organizacao,
            "papel_organizacao": v.papel_organizacao,
            "inativo": v.inativo,
            "created_at": v.created_at,
            "usuario_nome": v.usuario.nome if v.usuario else None,
            "usuario_login": v.usuario.usuario if v.usuario else None,
            "usuario_email": v.usuario.email if v.usuario else None,
        })

    return {
        "id": org.id,
        "nome": org.nome,
        "sigla": org.sigla,
        "descricao": org.descricao,
        "inativo": org.inativo,
        "created_at": org.created_at,
        "updated_at": org.updated_at,
        "unidades_count": unidades_count,
        "grupos_count": grupos_count,
        "usuarios_vinculos": vinculos_response
    }


def create_organizacao(db: Session, data: OrganizacaoCreate, current_user: Optional[Usuario] = None) -> Organizacao:
    nova_org = Organizacao(
        nome=data.nome,
        sigla=data.sigla,
        descricao=data.descricao
    )
    db.add(nova_org)
    db.flush()

    has_creator_link = False
    if data.usuarios_vinculos:
        for item in data.usuarios_vinculos:
            usuario = db.query(Usuario).filter(Usuario.id == item.id_usuario, Usuario.inativo == False).first()
            if usuario:
                vinculo = UsuarioOrganizacao(
                    id_usuario=item.id_usuario,
                    id_organizacao=nova_org.id,
                    papel_organizacao=item.papel_organizacao
                )
                db.add(vinculo)
                if current_user and str(item.id_usuario) == str(current_user.id):
                    has_creator_link = True

    # Se um usuário autenticado criou a organização e ainda não está nos vínculos, vincula-o como GESTOR
    if current_user and not has_creator_link:
        vinculo_criador = UsuarioOrganizacao(
            id_usuario=current_user.id,
            id_organizacao=nova_org.id,
            papel_organizacao=PapelOrganizacaoEnum.GESTOR
        )
        db.add(vinculo_criador)

    db.commit()
    db.refresh(nova_org)
    return nova_org


def update_organizacao(db: Session, id: UUID, data: OrganizacaoUpdate) -> Organizacao:
    org = get_by_id(db, id)
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(org, key, value)
    db.commit()
    db.refresh(org)
    return org


def deactivate_organizacao(db: Session, id: UUID) -> Organizacao:
    org = get_by_id(db, id)
    org.inativo = True
    db.commit()
    db.refresh(org)
    return org


def adicionar_vinculo_usuario(db: Session, org_id: UUID, item: UsuarioVinculoItem) -> UsuarioOrganizacao:
    org = get_by_id(db, org_id)
    usuario = db.query(Usuario).filter(Usuario.id == item.id_usuario, Usuario.inativo == False).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="user.not_found")

    vinculo = db.query(UsuarioOrganizacao).filter(
        UsuarioOrganizacao.id_organizacao == org_id,
        UsuarioOrganizacao.id_usuario == item.id_usuario
    ).first()

    if vinculo:
        vinculo.inativo = False
        vinculo.papel_organizacao = item.papel_organizacao
    else:
        vinculo = UsuarioOrganizacao(
            id_organizacao=org_id,
            id_usuario=item.id_usuario,
            papel_organizacao=item.papel_organizacao
        )
        db.add(vinculo)

    db.commit()
    db.refresh(vinculo)
    return vinculo


def atualizar_vinculo_usuario(db: Session, org_id: UUID, usuario_id: UUID, data: VinculoUpdateSchema) -> UsuarioOrganizacao:
    vinculo = db.query(UsuarioOrganizacao).filter(
        UsuarioOrganizacao.id_organizacao == org_id,
        UsuarioOrganizacao.id_usuario == usuario_id
    ).first()

    if not vinculo:
        raise HTTPException(status_code=404, detail="organization.user_link_not_found")

    vinculo.papel_organizacao = data.papel_organizacao
    if data.inativo is not None:
        vinculo.inativo = data.inativo

    db.commit()
    db.refresh(vinculo)
    return vinculo


def desativar_vinculo_usuario(db: Session, org_id: UUID, usuario_id: UUID):
    vinculo = db.query(UsuarioOrganizacao).filter(
        UsuarioOrganizacao.id_organizacao == org_id,
        UsuarioOrganizacao.id_usuario == usuario_id
    ).first()

    if not vinculo:
        raise HTTPException(status_code=404, detail="organization.link_not_found")

    vinculo.inativo = True
    db.commit()
    return {"success": True}


def listar_usuarios_detalhados_organizacao(db: Session, org_id: UUID):
    """
    Retorna os usuários vinculados à organização indicando:
    - Dados do usuário (nome, login, email)
    - Papel no vínculo da Organização (GESTOR ou MEMBRO)
    - Unidades das quais faz parte na Organização (via Perfil)
    - Grupos dos quais faz parte na Organização (via Atribuicao)
    """
    vinculos = (
        db.query(UsuarioOrganizacao)
        .options(
            joinedload(UsuarioOrganizacao.usuario).joinedload(Usuario.perfis).joinedload(Perfil.unidade),
            joinedload(UsuarioOrganizacao.usuario).joinedload(Usuario.atribuicoes).joinedload(Atribuicao.grupo),
        )
        .filter(UsuarioOrganizacao.id_organizacao == org_id, UsuarioOrganizacao.inativo == False)
        .all()
    )

    resultado = []
    for v in vinculos:
        usr = v.usuario
        if not usr or usr.inativo:
            continue

        # Unidades do usuário vinculadas a esta organização
        unidades_usuario = []
        for p in usr.perfis:
            if p.unidade and p.unidade.id_organizacao == org_id and not p.inativo and not p.unidade.inativo:
                unidades_usuario.append({
                    "id": p.unidade.id,
                    "nome": p.unidade.nome,
                    "sigla": p.unidade.sigla,
                    "papel_unidade": p.nivel.nome if p.nivel else "Membro da Unidade"
                })

        # Grupos do usuário vinculados a esta organização
        grupos_usuario = []
        for a in usr.atribuicoes:
            if a.grupo and a.grupo.id_organizacao == org_id and not a.inativo and not a.grupo.inativo:
                grupos_usuario.append({
                    "id": a.grupo.id,
                    "nome": a.grupo.nome,
                    "papel_grupo": a.nivel.nome if a.nivel else "Participante do Grupo"
                })

        resultado.append({
            "vinculo_id": v.id,
            "usuario_id": usr.id,
            "nome": usr.nome,
            "usuario": usr.usuario,
            "email": usr.email,
            "cpf": usr.cpf,
            "papel_organizacao": v.papel_organizacao,
            "unidades": unidades_usuario,
            "grupos": grupos_usuario
        })

    return resultado


def listar_usuarios_disponiveis_organizacao(
    db: Session,
    org_id: UUID,
    nome: Optional[str] = None,
    page: int = 0,
    size: int = 50
):
    """
    Retorna todos os usuários ativos e autorizados do sistema
    que ainda NÃO possuem vínculo ativo nesta organização.
    """
    vinculados_subquery = (
        db.query(UsuarioOrganizacao.id_usuario)
        .filter(
            UsuarioOrganizacao.id_organizacao == org_id,
            UsuarioOrganizacao.inativo == False
        )
    )

    query = db.query(Usuario).filter(
        Usuario.inativo == False,
        Usuario.is_autorizado == True,
        Usuario.id.notin_(vinculados_subquery)
    )

    if nome and nome.strip():
        search_term = f"%{nome.strip()}%"
        query = query.filter(
            (Usuario.nome.ilike(search_term)) |
            (Usuario.usuario.ilike(search_term)) |
            (Usuario.nickname.ilike(search_term)) |
            (Usuario.email.ilike(search_term))
        )

    total = query.count()
    items = query.order_by(Usuario.nome.asc()).offset(page * size).limit(size).all()

    return {
        "items": [
            {
                "id": str(u.id),
                "nome": u.nome,
                "usuario": u.usuario,
                "nickname": u.nickname,
                "email": u.email,
                "is_admin": u.is_admin,
            }
            for u in items
        ],
        "count": len(items),
        "total": total,
        "page": page,
        "size": size,
        "totalPages": math.ceil(total / size) if size > 0 else 0
    }

