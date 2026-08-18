from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.timezone import now_in_app_timezone
from app.models.meta import Meta
from app.models.entrega import Entrega
from app.models.unidade import Unidade
from app.models.enums import MetaStatusEnum, EntregaStatusEnum
from app.schemas.planejamento import MetaCreate, MetaUpdate, MetaResponse


def _calculate_progresso(meta: Meta, total_entregas: int, concluidas: int) -> float:
    val_inicial = float(meta.valor_meta_inicial or 0.0)
    val_pretendida = float(meta.valor_meta_pretendida or 0.0)
    val_atual = float(meta.valor_meta_atual or 0.0)

    if val_pretendida > val_inicial:
        progresso = ((val_atual - val_inicial) / (val_pretendida - val_inicial)) * 100.0
        return round(float(min(100.0, max(0.0, progresso))), 2)
    elif total_entregas > 0:
        return round(float((concluidas / total_entregas) * 100.0), 2)
    elif meta.status == MetaStatusEnum.CONCLUIDA:
        return 100.0
    return 0.0



def _build_meta_response(db: Session, meta: Meta) -> MetaResponse:
    entregas_query = db.query(Entrega).filter(
        Entrega.id_meta == meta.id,
        Entrega.inativo == False
    )
    total_entregas = entregas_query.count()
    concluidas = entregas_query.filter(Entrega.status == EntregaStatusEnum.ENTREGUE).count()

    progresso = _calculate_progresso(meta, total_entregas, concluidas)
    unidade_nome = meta.unidade.nome if meta.unidade else None

    return MetaResponse(
        id=meta.id,
        id_organizacao=meta.id_organizacao,
        id_unidade=meta.id_unidade,
        unidade_nome=unidade_nome,
        titulo=meta.titulo,
        descricao=meta.descricao,
        codigo=meta.codigo,
        valor_meta_inicial=float(meta.valor_meta_inicial or 0.0),
        valor_meta_pretendida=float(meta.valor_meta_pretendida or 0.0),
        valor_meta_atual=float(meta.valor_meta_atual or 0.0),
        progresso_percentual=progresso,
        total_entregas=total_entregas,
        total_entregas_concluidas=concluidas,
        data_inicio=meta.data_inicio,
        data_fim=meta.data_fim,
        status=meta.status,
        tipo_origem=meta.tipo_origem,
        inativo=meta.inativo,
        created_at=meta.created_at,
        updated_at=meta.updated_at,
        ativo=meta.ativo
    )


def list_all(
    db: Session,
    id_organizacao: UUID,
    page: int = 0,
    size: int = 10,
    id_unidade: UUID | None = None,
    status_filter: MetaStatusEnum | None = None,
    tipo_origem: str | None = None,
    q: str | None = None
) -> dict:
    query = db.query(Meta).filter(
        Meta.id_organizacao == id_organizacao,
        Meta.inativo == False
    )

    if id_unidade:
        query = query.filter(Meta.id_unidade == id_unidade)
    if status_filter:
        query = query.filter(Meta.status == status_filter)
    if tipo_origem:
        query = query.filter(Meta.tipo_origem == tipo_origem)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter((Meta.titulo.ilike(term)) | (Meta.codigo.ilike(term)))

    total = query.count()
    metas = query.order_by(Meta.created_at.desc()).offset(page * size).limit(size).all()

    items = [_build_meta_response(db, m) for m in metas]

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size if size > 0 else 0
    }


def get_by_id(db: Session, id_organizacao: UUID, meta_id: UUID) -> MetaResponse:
    meta = db.query(Meta).filter(
        Meta.id == meta_id,
        Meta.id_organizacao == id_organizacao,
        Meta.inativo == False
    ).first()

    if not meta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="meta.not_found")

    return _build_meta_response(db, meta)


def create(db: Session, id_organizacao: UUID, data: MetaCreate) -> MetaResponse:
    if data.id_unidade:
        unidade = db.query(Unidade).filter(
            Unidade.id == data.id_unidade,
            Unidade.id_organizacao == id_organizacao,
            Unidade.inativo == False
        ).first()
        if not unidade:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unit.not_found")

    meta = Meta(
        id_organizacao=id_organizacao,
        id_unidade=data.id_unidade,
        titulo=data.titulo,
        descricao=data.descricao,
        codigo=data.codigo,
        valor_meta_inicial=data.valor_meta_inicial,
        valor_meta_pretendida=data.valor_meta_pretendida,
        valor_meta_atual=data.valor_meta_atual,
        data_inicio=data.data_inicio,
        data_fim=data.data_fim,
        status=data.status,
        tipo_origem=data.tipo_origem,
        created_at=now_in_app_timezone(),
        ativo=True,
        inativo=False
    )
    db.add(meta)
    db.commit()
    db.refresh(meta)

    return _build_meta_response(db, meta)


def update(db: Session, id_organizacao: UUID, meta_id: UUID, data: MetaUpdate) -> MetaResponse:
    meta = db.query(Meta).filter(
        Meta.id == meta_id,
        Meta.id_organizacao == id_organizacao,
        Meta.inativo == False
    ).first()

    if not meta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="meta.not_found")

    update_dict = data.model_dump(exclude_unset=True)
    if "id_unidade" in update_dict and update_dict["id_unidade"]:
        unidade = db.query(Unidade).filter(
            Unidade.id == update_dict["id_unidade"],
            Unidade.id_organizacao == id_organizacao,
            Unidade.inativo == False
        ).first()
        if not unidade:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unit.not_found")

    for key, value in update_dict.items():
        setattr(meta, key, value)

    meta.updated_at = now_in_app_timezone()
    db.commit()
    db.refresh(meta)

    return _build_meta_response(db, meta)


def deactivate(db: Session, id_organizacao: UUID, meta_id: UUID) -> None:
    meta = db.query(Meta).filter(
        Meta.id == meta_id,
        Meta.id_organizacao == id_organizacao,
        Meta.inativo == False
    ).first()

    if not meta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="meta.not_found")

    meta.inativo = True
    meta.ativo = False
    meta.updated_at = now_in_app_timezone()
    db.commit()
