from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_active_organization
from app.core.response import success_response
from app.models.usuario import Usuario
from app.models.organizacao import Organizacao
from app.models.enums import OrigemDisparoEnum
from app.schemas.integracao import (
    IntegracaoConfigCreate,
    IntegracaoConfigUpdate,
    IntegracaoEndpointCreate,
    IntegracaoEndpointUpdate,
    TestConnectionRequest,
    InspectSchemaRequest,
    PreviewMappingRequest,
    PreviewSyncRequest,
    SyncNowRequest,
)
from app.services import integracao_service, schema_inspector_service, integration_engine_service

router = APIRouter(tags=["Integrações"])


@router.post("/test-connection")
async def test_external_connection(
    data: TestConnectionRequest,
    org: Organizacao = Depends(require_active_organization),
    current_user: Usuario = Depends(get_current_user)
):
    result = await schema_inspector_service.test_connection(data)
    return success_response(data=result, message="integration.connection_tested")


@router.post("/inspect-schema")
async def inspect_external_schema(
    data: InspectSchemaRequest,
    org: Organizacao = Depends(require_active_organization),
    current_user: Usuario = Depends(get_current_user)
):
    result = await schema_inspector_service.inspect_schema(data)
    return success_response(data=result, message="integration.schema_inspected")


@router.post("/preview-mapping")
async def preview_lego_mapping(
    data: PreviewMappingRequest,
    org: Organizacao = Depends(require_active_organization),
    current_user: Usuario = Depends(get_current_user)
):
    result = await schema_inspector_service.preview_mapping(data)
    return success_response(data=result, message="integration.mapping_previewed")


@router.get("/tarefas-live")
async def get_live_tasks(
    id_unidade: UUID | None = Query(None, description="Identificador opcional da unidade"),
    id_endpoint: UUID | None = Query(None, description="Identificador opcional do endpoint a ser consultado"),
    funcionalidade: str = Query("REGISTRO_DIARIO", description="Funcionalidade que está solicitando as tarefas"),
    data_referencia: str | None = Query(None, description="Data de referência para consulta (YYYY-MM-DD)"),
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    result = await integration_engine_service.fetch_live_user_tasks(
        db=db,
        id_organizacao=org.id,
        usuario=current_user,
        id_unidade=id_unidade,
        id_endpoint=id_endpoint,
        funcionalidade=funcionalidade,
        data_referencia=data_referencia,
    )
    return success_response(data=result.model_dump(mode='json'), message="integration.live_tasks_fetched")


# ==========================================
# CONEXÕES BASE (IntegracaoConfig)
# ==========================================

@router.get("/")
def list_integrations(
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = integracao_service.list_integracoes(db=db, id_organizacao=org.id)
    return success_response(data=result, message="integration.listed")


@router.get("/{id}")
def get_integration(
    id: UUID,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = integracao_service.get_integracao(db=db, id_organizacao=org.id, integracao_id=id)
    return success_response(data=result, message="integration.found")


@router.post("/")
def create_integration(
    data: IntegracaoConfigCreate,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = integracao_service.create_integracao(db=db, id_organizacao=org.id, data=data)
    return success_response(data=result, message="integration.created")


@router.put("/{id}")
def update_integration(
    id: UUID,
    data: IntegracaoConfigUpdate,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = integracao_service.update_integracao(db=db, id_organizacao=org.id, integracao_id=id, data=data)
    return success_response(data=result, message="integration.updated")


@router.delete("/{id}")
def delete_integration(
    id: UUID,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    integracao_service.delete_integracao(db=db, id_organizacao=org.id, integracao_id=id)
    return success_response(data=None, message="integration.deleted")


# ==========================================
# ENDPOINTS DE CONSULTA
# ==========================================

@router.get("/{id}/endpoints")
def list_integration_endpoints(
    id: UUID,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = integracao_service.list_endpoints(db=db, id_organizacao=org.id, integracao_id=id)
    return success_response(data=result, message="integration.endpoints_listed")


@router.post("/{id}/endpoints")
def create_integration_endpoint(
    id: UUID,
    data: IntegracaoEndpointCreate,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = integracao_service.create_endpoint(db=db, id_organizacao=org.id, integracao_id=id, data=data)
    return success_response(data=result, message="integration.endpoint_created")


@router.get("/{id}/endpoints/{endpoint_id}")
def get_integration_endpoint(
    id: UUID,
    endpoint_id: UUID,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = integracao_service.get_endpoint(db=db, id_organizacao=org.id, endpoint_id=endpoint_id)
    return success_response(data=result, message="integration.endpoint_found")


@router.put("/{id}/endpoints/{endpoint_id}")
def update_integration_endpoint(
    id: UUID,
    endpoint_id: UUID,
    data: IntegracaoEndpointUpdate,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = integracao_service.update_endpoint(db=db, id_organizacao=org.id, endpoint_id=endpoint_id, data=data)
    return success_response(data=result, message="integration.endpoint_updated")


@router.delete("/{id}/endpoints/{endpoint_id}")
def delete_integration_endpoint(
    id: UUID,
    endpoint_id: UUID,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    integracao_service.delete_endpoint(db=db, id_organizacao=org.id, endpoint_id=endpoint_id)
    return success_response(data=None, message="integration.endpoint_deleted")


# ==========================================
# HISTÓRICO E SINCRONIZAÇÃO
# ==========================================

@router.get("/{id}/historico")
def list_integration_history(
    id: UUID,
    endpoint_id: UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    result = integracao_service.list_historico_execucoes(
        db=db,
        id_organizacao=org.id,
        integracao_id=id,
        endpoint_id=endpoint_id,
        skip=skip,
        limit=limit,
    )
    return success_response(data=result, message="integration.history_listed")


@router.post("/{id}/sync-now")
async def sync_integration_now(
    id: UUID,
    payload: SyncNowRequest | None = None,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    # Verify integration belongs to active org
    integracao_service.get_integracao(db=db, id_organizacao=org.id, integracao_id=id)

    historicos = await integration_engine_service.run_integration_sync(
        db=db,
        integracao_id=id,
        disparo=OrigemDisparoEnum.MANUAL,
        id_usuario_executor=current_user.id,
        selected_external_ids=payload.selected_external_ids if payload else None,
        simulated_user_id=payload.id_usuario_simulacao if payload else None,
        simulated_unit_id=payload.id_unidade_simulacao if payload else None,
    )
    return success_response(data=[{
        "id_historico": h.id,
        "id_endpoint": h.id_integracao_endpoint,
        "status": h.status,
        "total_encontrados": h.total_encontrados,
        "total_criados": h.total_criados,
        "total_atualizados": h.total_atualizados,
        "total_inalterados": h.total_inalterados,
        "total_erros": h.total_erros,
        "data_inicio": h.data_inicio,
        "data_fim": h.data_fim,
    } for h in historicos], message="integration.sync_completed")


@router.post("/{id}/endpoints/{endpoint_id}/sync-now")
async def sync_endpoint_now(
    id: UUID,
    endpoint_id: UUID,
    payload: SyncNowRequest | None = None,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    integracao_service.get_endpoint(db=db, id_organizacao=org.id, endpoint_id=endpoint_id)

    historico = await integration_engine_service.run_endpoint_sync(
        db=db,
        endpoint_id=endpoint_id,
        disparo=OrigemDisparoEnum.MANUAL,
        id_usuario_executor=current_user.id,
        selected_external_ids=payload.selected_external_ids if payload else None,
        simulated_user_id=payload.id_usuario_simulacao if payload else None,
        simulated_unit_id=payload.id_unidade_simulacao if payload else None,
    )
    return success_response(data={
        "id_historico": historico.id,
        "id_endpoint": historico.id_integracao_endpoint,
        "status": historico.status,
        "total_encontrados": historico.total_encontrados,
        "total_criados": historico.total_criados,
        "total_atualizados": historico.total_atualizados,
        "total_inalterados": historico.total_inalterados,
        "total_erros": historico.total_erros,
        "data_inicio": historico.data_inicio,
        "data_fim": historico.data_fim,
    }, message="integration.sync_completed")


@router.post("/{id}/preview-sync")
async def preview_integration_sync(
    id: UUID,
    payload: PreviewSyncRequest | None = None,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    # Verify integration belongs to active org
    integracao_service.get_integracao(db=db, id_organizacao=org.id, integracao_id=id)

    preview = await integration_engine_service.preview_integration_sync(
        db=db,
        integracao_id=id,
        simulated_user_id=payload.id_usuario_simulacao if payload else None,
        simulated_unit_id=payload.id_unidade_simulacao if payload else None,
        current_user=current_user,
    )
    return success_response(data=preview.model_dump(mode='json'), message="integration.preview_generated")


@router.post("/{id}/endpoints/{endpoint_id}/preview-sync")
async def preview_endpoint_sync(
    id: UUID,
    endpoint_id: UUID,
    payload: PreviewSyncRequest | None = None,
    org: Organizacao = Depends(require_active_organization),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    integracao_service.get_endpoint(db=db, id_organizacao=org.id, endpoint_id=endpoint_id)

    preview = await integration_engine_service.preview_endpoint_sync(
        db=db,
        endpoint_id=endpoint_id,
        simulated_user_id=payload.id_usuario_simulacao if payload else None,
        simulated_unit_id=payload.id_unidade_simulacao if payload else None,
        current_user=current_user,
    )
    return success_response(data=preview.model_dump(mode='json'), message="integration.preview_generated")

