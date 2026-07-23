from uuid import UUID
from sqlalchemy.orm import Session, selectinload
from fastapi import HTTPException
from app.models.grupo import GrupoTrabalho
from app.models.atribuicao import Atribuicao
from app.models.nivel import Nivel
from app.schemas.grupo import GrupoCreate, GrupoUpdate
import math


def list_all(db: Session, page: int, size: int):
    query = db.query(GrupoTrabalho).options(
        selectinload(GrupoTrabalho.unidade)
    ).filter(GrupoTrabalho.inativo == False)
    total = query.count()
    items = query.offset(page * size).limit(size).all()
    return {
        "items": items,
        "count": len(items),
        "page": page,
        "size": size,
        "totalPages": math.ceil(total / size) if size > 0 else 0
    }


def get_by_id(db: Session, id: UUID) -> GrupoTrabalho:
    grupo = db.query(GrupoTrabalho).options(
        selectinload(GrupoTrabalho.atribuicoes).selectinload(Atribuicao.usuario),
        selectinload(GrupoTrabalho.atribuicoes).selectinload(Atribuicao.nivel),
        selectinload(GrupoTrabalho.unidade)
    ).filter(GrupoTrabalho.id == id, GrupoTrabalho.inativo == False).first()
    if not grupo:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    return grupo


def _assign_users_to_group(
    db: Session,
    grupo_id: UUID,
    usuarios_chefes: list[UUID],
    usuarios_participantes: list[UUID],
):
    if not usuarios_chefes:
        raise HTTPException(status_code=400, detail="O grupo deve ter pelo menos 1 chefe")
    if not usuarios_participantes:
        raise HTTPException(status_code=400, detail="O grupo deve ter pelo menos 1 participante")

    chefes_set = set(str(uid) for uid in usuarios_chefes)
    participantes_set = set(str(uid) for uid in usuarios_participantes)
    intersect = chefes_set.intersection(participantes_set)
    if intersect:
        raise HTTPException(
            status_code=400,
            detail="Um usuário não pode ser chefe e participante ao mesmo tempo",
        )

    nivel_chefe = db.query(Nivel).filter(Nivel.valor == 201).first()
    nivel_participante = db.query(Nivel).filter(Nivel.valor == 202).first()

    if not nivel_chefe or not nivel_participante:
        raise HTTPException(
            status_code=500,
            detail="Níveis 201 (Gestor) ou 202 (Participante) não configurados no sistema",
        )

    existing_atribuicoes = (
        db.query(Atribuicao).filter(Atribuicao.id_grupo == grupo_id).all()
    )
    existing_map = {str(a.id_usuario): a for a in existing_atribuicoes}

    target_assignments: dict[str, UUID] = {}
    for uid in usuarios_chefes:
        target_assignments[str(uid)] = nivel_chefe.id
    for uid in usuarios_participantes:
        target_assignments[str(uid)] = nivel_participante.id

    # Create or reactivate assignments
    for uid_str, nivel_id in target_assignments.items():
        if uid_str in existing_map:
            atrib = existing_map[uid_str]
            atrib.id_nivel = nivel_id
            atrib.inativo = False
        else:
            nova_atrib = Atribuicao(
                id_usuario=uid_str,
                id_grupo=grupo_id,
                id_nivel=nivel_id,
            )
            db.add(nova_atrib)

    # Deactivate removed assignments
    for uid_str, atrib in existing_map.items():
        if uid_str not in target_assignments:
            atrib.inativo = True


def create_in_unidade(db: Session, unidade_id: UUID, data: GrupoCreate) -> GrupoTrabalho:
    novo_grupo = GrupoTrabalho(
        nome=data.nome,
        id_unidade=unidade_id,
        inativo=data.inativo,
    )
    db.add(novo_grupo)
    db.flush()

    _assign_users_to_group(
        db,
        novo_grupo.id,
        data.usuarios_chefes,
        data.usuarios_participantes,
    )

    db.commit()
    db.refresh(novo_grupo)
    return novo_grupo


def update_in_unidade(
    db: Session, unidade_id: UUID, grupo_id: UUID, data: GrupoUpdate
) -> GrupoTrabalho:
    grupo = get_by_id(db, grupo_id)
    if str(grupo.id_unidade) != str(unidade_id):
        raise HTTPException(status_code=400, detail="Grupo não pertence a esta unidade")

    update_data = data.model_dump(
        exclude_unset=True, exclude={"usuarios_chefes", "usuarios_participantes"}
    )
    for key, value in update_data.items():
        setattr(grupo, key, value)

    db.flush()

    if data.usuarios_chefes is not None and data.usuarios_participantes is not None:
        _assign_users_to_group(
            db,
            grupo.id,
            data.usuarios_chefes,
            data.usuarios_participantes,
        )

    db.commit()
    db.refresh(grupo)
    return grupo


def deactivate(db: Session, id: UUID):
    grupo = get_by_id(db, id)
    grupo.inativo = True
    db.commit()
    db.refresh(grupo)
    return grupo
