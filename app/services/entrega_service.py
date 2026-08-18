from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.timezone import now_in_app_timezone
from app.models.entrega import Entrega
from app.models.meta import Meta
from app.models.unidade import Unidade
from app.models.usuario import Usuario
from app.models.enums import EntregaStatusEnum, OrigemEntregaEnum
from app.schemas.planejamento import EntregaCreate, EntregaUpdate, EntregaResponse, EntregaResumoResponse


def _build_entrega_response(entrega: Entrega) -> EntregaResponse:
    meta_titulo = entrega.meta.titulo if entrega.meta else None
    unidade_nome = entrega.unidade.nome if entrega.unidade else None
    usuario_nome = entrega.usuario_responsavel.nome if entrega.usuario_responsavel else None

    return EntregaResponse(
        id=entrega.id,
        id_organizacao=entrega.id_organizacao,
        id_meta=entrega.id_meta,
        meta_titulo=meta_titulo,
        id_unidade=entrega.id_unidade,
        unidade_nome=unidade_nome,
        id_usuario_responsavel=entrega.id_usuario_responsavel,
        usuario_responsavel_nome=usuario_nome,
        id_integracao_config=entrega.id_integracao_config,
        external_id=entrega.external_id,
        titulo=entrega.titulo,
        descricao=entrega.descricao,
        tipo_origem=entrega.tipo_origem,
        data_inicio=entrega.data_inicio,
        data_fim=entrega.data_fim,
        data_conclusao=entrega.data_conclusao,
        status=entrega.status,
        progresso_percentual=entrega.progresso_percentual,
        external_data=entrega.external_data,
        inativo=entrega.inativo,
        created_at=entrega.created_at,
        updated_at=entrega.updated_at,
        ativo=entrega.ativo
    )


def list_all(
    db: Session,
    id_organizacao: UUID,
    page: int = 0,
    size: int = 10,
    id_meta: UUID | None = None,
    id_unidade: UUID | None = None,
    id_usuario_responsavel: UUID | None = None,
    status_filter: EntregaStatusEnum | None = None,
    tipo_origem: OrigemEntregaEnum | None = None,
    q: str | None = None
) -> dict:
    query = db.query(Entrega).filter(
        Entrega.id_organizacao == id_organizacao,
        Entrega.inativo == False
    )

    if id_meta:
        query = query.filter(Entrega.id_meta == id_meta)
    if id_unidade:
        query = query.filter(Entrega.id_unidade == id_unidade)
    if id_usuario_responsavel:
        query = query.filter(Entrega.id_usuario_responsavel == id_usuario_responsavel)
    if status_filter:
        query = query.filter(Entrega.status == status_filter)
    if tipo_origem:
        query = query.filter(Entrega.tipo_origem == tipo_origem)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter((Entrega.titulo.ilike(term)) | (Entrega.descricao.ilike(term)))

    total = query.count()
    entregas = query.order_by(Entrega.created_at.desc()).offset(page * size).limit(size).all()

    items = [_build_entrega_response(e) for e in entregas]

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size if size > 0 else 0
    }


def list_resumo_by_unidade(
    db: Session,
    id_organizacao: UUID,
    id_unidade: UUID | None = None
) -> list[EntregaResumoResponse]:
    query = db.query(Entrega).filter(
        Entrega.id_organizacao == id_organizacao,
        Entrega.inativo == False
    )

    if id_unidade:
        query = query.filter(
            (Entrega.id_unidade == id_unidade) | (Entrega.id_unidade.is_(None))
        )

    entregas = query.order_by(Entrega.titulo.asc()).all()

    return [
        EntregaResumoResponse(
            id=e.id,
            titulo=e.titulo,
            tipo_origem=e.tipo_origem,
            status=e.status,
            progresso_percentual=e.progresso_percentual,
            data_fim=e.data_fim,
            id_meta=e.id_meta,
            meta_titulo=e.meta.titulo if e.meta else None,
            id_unidade=e.id_unidade,
            unidade_nome=e.unidade.nome if e.unidade else None
        )
        for e in entregas
    ]


def get_by_id(db: Session, id_organizacao: UUID, entrega_id: UUID) -> EntregaResponse:
    entrega = db.query(Entrega).filter(
        Entrega.id == entrega_id,
        Entrega.id_organizacao == id_organizacao,
        Entrega.inativo == False
    ).first()

    if not entrega:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="delivery.not_found")

    return _build_entrega_response(entrega)


def create(db: Session, id_organizacao: UUID, data: EntregaCreate) -> EntregaResponse:
    if data.id_meta:
        meta = db.query(Meta).filter(
            Meta.id == data.id_meta,
            Meta.id_organizacao == id_organizacao,
            Meta.inativo == False
        ).first()
        if not meta:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="meta.not_found")

    if data.id_unidade:

        unidade = db.query(Unidade).filter(
            Unidade.id == data.id_unidade,
            Unidade.id_organizacao == id_organizacao,
            Unidade.inativo == False
        ).first()
        if not unidade:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unit.not_found")

    if data.id_usuario_responsavel:
        usuario = db.query(Usuario).filter(
            Usuario.id == data.id_usuario_responsavel,
            Usuario.inativo == False
        ).first()
        if not usuario:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user.not_found")

    entrega = Entrega(
        id_organizacao=id_organizacao,
        id_meta=data.id_meta,
        id_unidade=data.id_unidade,
        id_usuario_responsavel=data.id_usuario_responsavel,
        external_id=data.external_id,
        titulo=data.titulo,
        descricao=data.descricao,
        tipo_origem=data.tipo_origem,
        data_inicio=data.data_inicio,
        data_fim=data.data_fim,
        data_conclusao=data.data_conclusao,
        status=data.status,
        progresso_percentual=data.progresso_percentual,
        external_data=data.external_data,
        created_at=now_in_app_timezone(),
        ativo=True,
        inativo=False
    )
    db.add(entrega)
    db.commit()
    db.refresh(entrega)

    return _build_entrega_response(entrega)


def update(db: Session, id_organizacao: UUID, entrega_id: UUID, data: EntregaUpdate) -> EntregaResponse:
    entrega = db.query(Entrega).filter(
        Entrega.id == entrega_id,
        Entrega.id_organizacao == id_organizacao,
        Entrega.inativo == False
    ).first()

    if not entrega:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="delivery.not_found")

    update_dict = data.model_dump(exclude_unset=True)

    if "id_meta" in update_dict and update_dict["id_meta"]:
        meta = db.query(Meta).filter(
            Meta.id == update_dict["id_meta"],
            Meta.id_organizacao == id_organizacao,
            Meta.inativo == False
        ).first()
        if not meta:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="meta.not_found")

    if "id_unidade" in update_dict and update_dict["id_unidade"]:
        unidade = db.query(Unidade).filter(
            Unidade.id == update_dict["id_unidade"],
            Unidade.id_organizacao == id_organizacao,
            Unidade.inativo == False
        ).first()
        if not unidade:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unit.not_found")

    if "id_usuario_responsavel" in update_dict and update_dict["id_usuario_responsavel"]:
        usuario = db.query(Usuario).filter(
            Usuario.id == update_dict["id_usuario_responsavel"],
            Usuario.inativo == False
        ).first()
        if not usuario:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user.not_found")

    for key, value in update_dict.items():
        setattr(entrega, key, value)

    entrega.updated_at = now_in_app_timezone()
    db.commit()
    db.refresh(entrega)

    return _build_entrega_response(entrega)


def deactivate(db: Session, id_organizacao: UUID, entrega_id: UUID) -> None:
    entrega = db.query(Entrega).filter(
        Entrega.id == entrega_id,
        Entrega.id_organizacao == id_organizacao,
        Entrega.inativo == False
    ).first()

    if not entrega:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="delivery.not_found")

    entrega.inativo = True
    entrega.ativo = False
    entrega.updated_at = now_in_app_timezone()
    db.commit()
