from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from fastapi import HTTPException

from app.core.timezone import now_in_app_timezone
from app.models.enums import StatusIntegracaoEnum
from app.models.integracao_config import IntegracaoConfig
from app.models.integracao_endpoint import IntegracaoEndpoint
from app.models.integracao_mapeamento import IntegracaoMapeamento
from app.models.integracao_execucao_historico import IntegracaoExecucaoHistorico
from app.models.entrega import Entrega
from app.models.meta import Meta
from app.models.unidade import Unidade
from app.models.usuario import Usuario
from app.schemas.integracao import (
    IntegracaoConfigCreate,
    IntegracaoConfigUpdate,
    IntegracaoConfigResponse,
    IntegracaoEndpointCreate,
    IntegracaoEndpointUpdate,
    IntegracaoEndpointResponse,
    IntegracaoMapeamentoCreate,
    IntegracaoMapeamentoUpdate,
    IntegracaoMapeamentoResponse,
    IntegracaoExecucaoHistoricoResponse,
    ParametroConfigSchema,
)


def _format_mapeamento_response(map_obj: IntegracaoMapeamento, db: Session) -> IntegracaoMapeamentoResponse:
    meta_titulo = None
    if map_obj.default_id_meta:
        meta = db.query(Meta).filter(Meta.id == map_obj.default_id_meta).first()
        meta_titulo = meta.titulo if meta else None

    unidade_nome = None
    if map_obj.default_id_unidade:
        unidade = db.query(Unidade).filter(Unidade.id == map_obj.default_id_unidade).first()
        unidade_nome = unidade.nome if unidade else None

    return IntegracaoMapeamentoResponse(
        id=map_obj.id,
        id_integracao_endpoint=map_obj.id_integracao_endpoint,
        items_root_path=map_obj.items_root_path,
        external_id_mode=map_obj.external_id_mode,
        external_id_path=map_obj.external_id_path,
        external_id_composite_paths=map_obj.external_id_composite_paths,
        external_id_composite_template=map_obj.external_id_composite_template,
        campo_titulo=map_obj.campo_titulo,
        campo_descricao=map_obj.campo_descricao,
        campo_codigo=map_obj.campo_codigo,
        campo_data_inicio=map_obj.campo_data_inicio,
        campo_data_fim=map_obj.campo_data_fim,
        campo_data_conclusao=map_obj.campo_data_conclusao,
        campo_status=map_obj.campo_status,
        map_status_values=map_obj.map_status_values,
        campo_progresso=map_obj.campo_progresso,
        campo_valor_inicial=map_obj.campo_valor_inicial,
        campo_valor_pretendido=map_obj.campo_valor_pretendido,
        campo_valor_atual=map_obj.campo_valor_atual,
        campo_responsavel=map_obj.campo_responsavel,
        campo_tipo_anotacao=map_obj.campo_tipo_anotacao,
        campo_meta_id=map_obj.campo_meta_id,
        campo_meta_titulo=map_obj.campo_meta_titulo,
        campo_unidade_origem=map_obj.campo_unidade_origem,
        campo_projeto=map_obj.campo_projeto,
        campo_prioridade=map_obj.campo_prioridade,
        campo_autor=map_obj.campo_autor,
        campo_data_atualizacao=map_obj.campo_data_atualizacao,
        campo_link_externo=map_obj.campo_link_externo,
        campos_extras=map_obj.campos_extras,
        map_unidades_values=map_obj.map_unidades_values,
        map_usuarios_values=map_obj.map_usuarios_values,
        regras_de_para=map_obj.regras_de_para or [],
        default_id_meta=map_obj.default_id_meta,
        default_meta_titulo=meta_titulo,
        default_id_unidade=map_obj.default_id_unidade,
        default_unidade_nome=unidade_nome,
        regras_transformacao=map_obj.regras_transformacao,
        inativo=map_obj.inativo,
        created_at=map_obj.created_at,
        updated_at=map_obj.updated_at,
        ativo=map_obj.ativo,
    )


def _format_endpoint_response(ep: IntegracaoEndpoint, db: Session) -> IntegracaoEndpointResponse:
    last_exec = db.query(IntegracaoExecucaoHistorico).filter(
        IntegracaoExecucaoHistorico.id_integracao_endpoint == ep.id,
        IntegracaoExecucaoHistorico.inativo == False
    ).order_by(desc(IntegracaoExecucaoHistorico.data_inicio)).first()

    total_synced = 0
    if ep.tipo_integracao.value == "RECEBER_METAS":
        total_synced = db.query(func.count(Meta.id)).filter(
            Meta.id_integracao_endpoint == ep.id,
            Meta.inativo == False
        ).scalar() or 0
    else:
        total_synced = db.query(func.count(Entrega.id)).filter(
            Entrega.id_integracao_endpoint == ep.id,
            Entrega.inativo == False
        ).scalar() or 0

    map_resp = None
    if ep.mapeamento and not ep.mapeamento.inativo:
        map_resp = _format_mapeamento_response(ep.mapeamento, db)

    params = []
    if ep.parametros_config:
        for p in ep.parametros_config:
            if isinstance(p, dict):
                params.append(ParametroConfigSchema(**p))
            elif isinstance(p, ParametroConfigSchema):
                params.append(p)

    return IntegracaoEndpointResponse(
        id=ep.id,
        id_integracao_config=ep.id_integracao_config,
        nome=ep.nome,
        tipo_integracao=ep.tipo_integracao,
        path=ep.path,
        metodo_http=ep.metodo_http,
        modo_execucao=ep.modo_execucao,
        parametros_config=params,
        headers_custom=ep.headers_custom,
        corpo_requisicao=ep.corpo_requisicao,
        escopo_unidades=ep.escopo_unidades,
        unidades_selecionadas=ep.unidades_selecionadas,
        escopo_usuarios=ep.escopo_usuarios,
        usuarios_selecionados=ep.usuarios_selecionados,
        ativo_sincronizacao=ep.ativo_sincronizacao,
        frequencia_cron=ep.frequencia_cron,
        funcionalidades_habilitadas=ep.funcionalidades_habilitadas or ["GESTAO_INTEGRACOES", "REGISTRO_DIARIO"],
        inativo=ep.inativo,
        created_at=ep.created_at,
        updated_at=ep.updated_at,
        ativo=ep.ativo,
        mapeamento=map_resp,
        ultima_execucao_status=last_exec.status if last_exec else None,
        ultima_execucao_data=last_exec.data_inicio if last_exec else None,
        total_registros_sincronizados=total_synced,
    )


def _format_config_response(cfg: IntegracaoConfig, db: Session) -> IntegracaoConfigResponse:
    last_exec = db.query(IntegracaoExecucaoHistorico).filter(
        IntegracaoExecucaoHistorico.id_integracao_config == cfg.id,
        IntegracaoExecucaoHistorico.inativo == False
    ).order_by(desc(IntegracaoExecucaoHistorico.data_inicio)).first()

    total_entregas = db.query(func.count(Entrega.id)).filter(
        Entrega.id_integracao_config == cfg.id,
        Entrega.id_organizacao == cfg.id_organizacao,
        Entrega.inativo == False
    ).scalar() or 0

    total_metas = db.query(func.count(Meta.id)).filter(
        Meta.id_integracao_config == cfg.id,
        Meta.id_organizacao == cfg.id_organizacao,
        Meta.inativo == False
    ).scalar() or 0

    endpoints_resp = [
        _format_endpoint_response(ep, db)
        for ep in cfg.endpoints
        if not ep.inativo
    ]

    return IntegracaoConfigResponse(
        id=cfg.id,
        id_organizacao=cfg.id_organizacao,
        nome=cfg.nome,
        descricao=cfg.descricao,
        status=cfg.status,
        provedor=cfg.provedor,
        url_base=cfg.url_base,
        tipo_autenticacao=cfg.tipo_autenticacao,
        auth_endpoint_path=cfg.auth_endpoint_path,
        auth_metodo_http=cfg.auth_metodo_http,
        auth_headers=cfg.auth_headers,
        auth_payload=cfg.auth_payload,
        auth_token_path=cfg.auth_token_path,
        auth_static_config=cfg.auth_static_config,
        headers_padrao=cfg.headers_padrao,
        ativo_sincronizacao=cfg.ativo_sincronizacao,
        frequencia_cron=cfg.frequencia_cron,
        id_agendamento=cfg.id_agendamento,
        inativo=cfg.inativo,
        created_at=cfg.created_at,
        updated_at=cfg.updated_at,
        ativo=cfg.ativo,
        endpoints=endpoints_resp,
        ultima_execucao_status=last_exec.status if last_exec else None,
        ultima_execucao_data=last_exec.data_inicio if last_exec else None,
        total_registros_sincronizados=total_entregas + total_metas,
    )


# ==========================================
# CRUD CONEXÕES BASE (IntegracaoConfig)
# ==========================================

def list_integracoes(db: Session, id_organizacao: UUID) -> list[IntegracaoConfigResponse]:
    configs = db.query(IntegracaoConfig).filter(
        IntegracaoConfig.id_organizacao == id_organizacao,
        IntegracaoConfig.inativo == False
    ).order_by(desc(IntegracaoConfig.created_at)).all()

    return [_format_config_response(c, db) for c in configs]


def get_integracao(db: Session, id_organizacao: UUID, integracao_id: UUID) -> IntegracaoConfigResponse:
    cfg = db.query(IntegracaoConfig).filter(
        IntegracaoConfig.id == integracao_id,
        IntegracaoConfig.id_organizacao == id_organizacao,
        IntegracaoConfig.inativo == False
    ).first()

    if not cfg:
        raise HTTPException(status_code=404, detail="integration.not_found")

    return _format_config_response(cfg, db)


def create_integracao(db: Session, id_organizacao: UUID, data: IntegracaoConfigCreate) -> IntegracaoConfigResponse:
    cfg = IntegracaoConfig(
        id_organizacao=id_organizacao,
        nome=data.nome,
        descricao=data.descricao,
        status=data.status,
        provedor=data.provedor,
        url_base=data.url_base,
        tipo_autenticacao=data.tipo_autenticacao,
        auth_endpoint_path=data.auth_endpoint_path,
        auth_metodo_http=data.auth_metodo_http,
        auth_headers=data.auth_headers,
        auth_payload=data.auth_payload,
        auth_token_path=data.auth_token_path,
        auth_static_config=data.auth_static_config,
        headers_padrao=data.headers_padrao,
        ativo_sincronizacao=data.ativo_sincronizacao,
        frequencia_cron=data.frequencia_cron,
        inativo=False,
        ativo=True,
    )
    db.add(cfg)
    db.flush()

    # Create initial endpoints if provided
    if data.endpoints:
        for ep_data in data.endpoints:
            params_raw = [p.model_dump(mode='json') for p in ep_data.parametros_config] if ep_data.parametros_config else None
            unidades_raw = [str(u) for u in ep_data.unidades_selecionadas] if ep_data.unidades_selecionadas else None
            usuarios_raw = [str(usr) for usr in ep_data.usuarios_selecionados] if ep_data.usuarios_selecionados else None
            ep = IntegracaoEndpoint(
                id_integracao_config=cfg.id,
                nome=ep_data.nome,
                tipo_integracao=ep_data.tipo_integracao,
                path=ep_data.path,
                metodo_http=ep_data.metodo_http,
                modo_execucao=ep_data.modo_execucao,
                parametros_config=params_raw,
                headers_custom=ep_data.headers_custom,
                corpo_requisicao=ep_data.corpo_requisicao,
                escopo_unidades=ep_data.escopo_unidades or 'TODAS',
                unidades_selecionadas=unidades_raw,
                escopo_usuarios=ep_data.escopo_usuarios or 'TODOS',
                usuarios_selecionados=usuarios_raw,
                ativo_sincronizacao=ep_data.ativo_sincronizacao,
                frequencia_cron=ep_data.frequencia_cron,
                funcionalidades_habilitadas=ep_data.funcionalidades_habilitadas or ["GESTAO_INTEGRACOES", "REGISTRO_DIARIO"],
                inativo=False,
                ativo=True,
            )
            db.add(ep)
            db.flush()

            if ep_data.mapeamento:
                m = ep_data.mapeamento
                map_obj = IntegracaoMapeamento(
                    id_integracao_endpoint=ep.id,
                    items_root_path=m.items_root_path,
                    external_id_mode=m.external_id_mode,
                    external_id_path=m.external_id_path,
                    external_id_composite_paths=m.external_id_composite_paths,
                    external_id_composite_template=m.external_id_composite_template,
                    campo_titulo=m.campo_titulo,
                    campo_descricao=m.campo_descricao,
                    campo_codigo=m.campo_codigo,
                    campo_data_inicio=m.campo_data_inicio,
                    campo_data_fim=m.campo_data_fim,
                    campo_data_conclusao=m.campo_data_conclusao,
                    campo_status=m.campo_status,
                    map_status_values=m.map_status_values,
                    campo_progresso=m.campo_progresso,
                    campo_valor_inicial=m.campo_valor_inicial,
                    campo_valor_pretendido=m.campo_valor_pretendido,
                    campo_valor_atual=m.campo_valor_atual,
                    campo_responsavel=m.campo_responsavel,
                    campo_tipo_anotacao=m.campo_tipo_anotacao,
                    campo_meta_id=m.campo_meta_id,
                    campo_meta_titulo=m.campo_meta_titulo,
                    campo_unidade_origem=m.campo_unidade_origem,
                    campo_projeto=m.campo_projeto,
                    campo_prioridade=m.campo_prioridade,
                    campo_autor=m.campo_autor,
                    campo_data_atualizacao=m.campo_data_atualizacao,
                    campo_link_externo=m.campo_link_externo,
                    campos_extras=m.campos_extras,
                    map_unidades_values=[u.model_dump(mode='json') for u in m.map_unidades_values] if m.map_unidades_values else None,
                    map_usuarios_values=[usr.model_dump(mode='json') for usr in m.map_usuarios_values] if m.map_usuarios_values else None,
                    regras_de_para=[r.model_dump(mode='json') for r in m.regras_de_para] if m.regras_de_para else [],
                    default_id_meta=m.default_id_meta,
                    default_id_unidade=m.default_id_unidade,
                    regras_transformacao=m.regras_transformacao,
                    inativo=False,
                    ativo=True,
                )
                db.add(map_obj)

    db.commit()
    db.refresh(cfg)
    return _format_config_response(cfg, db)


def update_integracao(db: Session, id_organizacao: UUID, integracao_id: UUID, data: IntegracaoConfigUpdate) -> IntegracaoConfigResponse:
    cfg = db.query(IntegracaoConfig).filter(
        IntegracaoConfig.id == integracao_id,
        IntegracaoConfig.id_organizacao == id_organizacao,
        IntegracaoConfig.inativo == False
    ).first()

    if not cfg:
        raise HTTPException(status_code=404, detail="integration.not_found")

    if data.nome is not None:
        cfg.nome = data.nome
    if data.descricao is not None:
        cfg.descricao = data.descricao
    if data.status is not None:
        cfg.status = data.status
        cfg.ativo = (data.status != StatusIntegracaoEnum.INATIVO)
    if data.provedor is not None:
        cfg.provedor = data.provedor
    if data.url_base is not None:
        cfg.url_base = data.url_base
    if data.tipo_autenticacao is not None:
        cfg.tipo_autenticacao = data.tipo_autenticacao
    if data.auth_endpoint_path is not None:
        cfg.auth_endpoint_path = data.auth_endpoint_path
    if data.auth_metodo_http is not None:
        cfg.auth_metodo_http = data.auth_metodo_http
    if data.auth_headers is not None:
        cfg.auth_headers = data.auth_headers
    if data.auth_payload is not None:
        cfg.auth_payload = data.auth_payload
    if data.auth_token_path is not None:
        cfg.auth_token_path = data.auth_token_path
    if data.auth_static_config is not None:
        cfg.auth_static_config = data.auth_static_config
    if data.headers_padrao is not None:
        cfg.headers_padrao = data.headers_padrao
    if data.ativo_sincronizacao is not None:
        cfg.ativo_sincronizacao = data.ativo_sincronizacao
    if data.frequencia_cron is not None:
        cfg.frequencia_cron = data.frequencia_cron

    # Update or recreate endpoints if provided
    if data.endpoints is not None:
        # Soft delete existing active endpoints and their mappings
        for existing_ep in cfg.endpoints:
            if not existing_ep.inativo:
                existing_ep.inativo = True
                if existing_ep.mapeamento and not existing_ep.mapeamento.inativo:
                    existing_ep.mapeamento.inativo = True

        # Create new endpoints with their mappings
        for ep_data in data.endpoints:
            params_raw = [p.model_dump(mode='json') for p in ep_data.parametros_config] if ep_data.parametros_config else None
            unidades_raw = [str(u) for u in ep_data.unidades_selecionadas] if ep_data.unidades_selecionadas else None
            usuarios_raw = [str(usr) for usr in ep_data.usuarios_selecionados] if ep_data.usuarios_selecionados else None
            new_ep = IntegracaoEndpoint(
                id_integracao_config=cfg.id,
                nome=ep_data.nome,
                tipo_integracao=ep_data.tipo_integracao,
                path=ep_data.path,
                metodo_http=ep_data.metodo_http,
                modo_execucao=ep_data.modo_execucao,
                parametros_config=params_raw,
                headers_custom=ep_data.headers_custom,
                corpo_requisicao=ep_data.corpo_requisicao,
                escopo_unidades=ep_data.escopo_unidades or 'TODAS',
                unidades_selecionadas=unidades_raw,
                escopo_usuarios=ep_data.escopo_usuarios or 'TODOS',
                usuarios_selecionados=usuarios_raw,
                ativo_sincronizacao=ep_data.ativo_sincronizacao,
                frequencia_cron=ep_data.frequencia_cron,
                funcionalidades_habilitadas=ep_data.funcionalidades_habilitadas or ["GESTAO_INTEGRACOES", "REGISTRO_DIARIO"],
                inativo=False,
                ativo=True,
            )
            db.add(new_ep)
            db.flush()

            if ep_data.mapeamento:
                m = ep_data.mapeamento
                map_obj = IntegracaoMapeamento(
                    id_integracao_endpoint=new_ep.id,
                    items_root_path=m.items_root_path,
                    external_id_mode=m.external_id_mode,
                    external_id_path=m.external_id_path,
                    external_id_composite_paths=m.external_id_composite_paths,
                    external_id_composite_template=m.external_id_composite_template,
                    campo_titulo=m.campo_titulo,
                    campo_descricao=m.campo_descricao,
                    campo_codigo=m.campo_codigo,
                    campo_data_inicio=m.campo_data_inicio,
                    campo_data_fim=m.campo_data_fim,
                    campo_data_conclusao=m.campo_data_conclusao,
                    campo_status=m.campo_status,
                    map_status_values=m.map_status_values,
                    campo_progresso=m.campo_progresso,
                    campo_valor_inicial=m.campo_valor_inicial,
                    campo_valor_pretendido=m.campo_valor_pretendido,
                    campo_valor_atual=m.campo_valor_atual,
                    campo_responsavel=m.campo_responsavel,
                    campo_tipo_anotacao=m.campo_tipo_anotacao,
                    campo_meta_id=m.campo_meta_id,
                    campo_meta_titulo=m.campo_meta_titulo,
                    campo_unidade_origem=m.campo_unidade_origem,
                    campo_projeto=m.campo_projeto,
                    campo_prioridade=m.campo_prioridade,
                    campo_autor=m.campo_autor,
                    campo_data_atualizacao=m.campo_data_atualizacao,
                    campo_link_externo=m.campo_link_externo,
                    campos_extras=m.campos_extras,
                    map_unidades_values=[u.model_dump(mode='json') for u in m.map_unidades_values] if m.map_unidades_values else None,
                    map_usuarios_values=[usr.model_dump(mode='json') for usr in m.map_usuarios_values] if m.map_usuarios_values else None,
                    regras_de_para=[r.model_dump(mode='json') for r in m.regras_de_para] if m.regras_de_para else [],
                    default_id_meta=m.default_id_meta,
                    default_id_unidade=m.default_id_unidade,
                    regras_transformacao=m.regras_transformacao,
                    inativo=False,
                    ativo=True,
                )
                db.add(map_obj)

    cfg.updated_at = now_in_app_timezone()
    db.commit()
    db.refresh(cfg)
    return _format_config_response(cfg, db)


def delete_integracao(db: Session, id_organizacao: UUID, integracao_id: UUID) -> None:
    cfg = db.query(IntegracaoConfig).filter(
        IntegracaoConfig.id == integracao_id,
        IntegracaoConfig.id_organizacao == id_organizacao,
        IntegracaoConfig.inativo == False
    ).first()

    if not cfg:
        raise HTTPException(status_code=404, detail="integration.not_found")

    cfg.inativo = True
    cfg.ativo = False
    cfg.updated_at = now_in_app_timezone()

    for ep in cfg.endpoints:
        ep.inativo = True
        ep.ativo = False
        ep.updated_at = now_in_app_timezone()
        if ep.mapeamento:
            ep.mapeamento.inativo = True
            ep.mapeamento.ativo = False

    db.commit()


# ==========================================
# CRUD ENDPOINTS (IntegracaoEndpoint)
# ==========================================

def list_endpoints(db: Session, id_organizacao: UUID, integracao_id: UUID) -> list[IntegracaoEndpointResponse]:
    cfg = db.query(IntegracaoConfig).filter(
        IntegracaoConfig.id == integracao_id,
        IntegracaoConfig.id_organizacao == id_organizacao,
        IntegracaoConfig.inativo == False
    ).first()

    if not cfg:
        raise HTTPException(status_code=404, detail="integration.not_found")

    endpoints = db.query(IntegracaoEndpoint).filter(
        IntegracaoEndpoint.id_integracao_config == cfg.id,
        IntegracaoEndpoint.inativo == False
    ).order_by(desc(IntegracaoEndpoint.created_at)).all()

    return [_format_endpoint_response(ep, db) for ep in endpoints]


def get_endpoint(db: Session, id_organizacao: UUID, endpoint_id: UUID) -> IntegracaoEndpointResponse:
    ep = db.query(IntegracaoEndpoint).join(
        IntegracaoConfig, IntegracaoConfig.id == IntegracaoEndpoint.id_integracao_config
    ).filter(
        IntegracaoEndpoint.id == endpoint_id,
        IntegracaoConfig.id_organizacao == id_organizacao,
        IntegracaoEndpoint.inativo == False,
        IntegracaoConfig.inativo == False
    ).first()

    if not ep:
        raise HTTPException(status_code=404, detail="integration.endpoint_not_found")

    return _format_endpoint_response(ep, db)


def create_endpoint(db: Session, id_organizacao: UUID, integracao_id: UUID, data: IntegracaoEndpointCreate) -> IntegracaoEndpointResponse:
    cfg = db.query(IntegracaoConfig).filter(
        IntegracaoConfig.id == integracao_id,
        IntegracaoConfig.id_organizacao == id_organizacao,
        IntegracaoConfig.inativo == False
    ).first()

    if not cfg:
        raise HTTPException(status_code=404, detail="integration.not_found")

    params_raw = [p.model_dump(mode='json') for p in data.parametros_config] if data.parametros_config else None
    ep = IntegracaoEndpoint(
        id_integracao_config=cfg.id,
        nome=data.nome,
        tipo_integracao=data.tipo_integracao,
        path=data.path,
        metodo_http=data.metodo_http,
        modo_execucao=data.modo_execucao,
        parametros_config=params_raw,
        headers_custom=data.headers_custom,
        corpo_requisicao=data.corpo_requisicao,
        ativo_sincronizacao=data.ativo_sincronizacao,
        frequencia_cron=data.frequencia_cron,
        funcionalidades_habilitadas=data.funcionalidades_habilitadas or ["GESTAO_INTEGRACOES", "REGISTRO_DIARIO"],
        inativo=False,
        ativo=True,
    )
    db.add(ep)
    db.flush()

    if data.mapeamento:
        m = data.mapeamento
        map_obj = IntegracaoMapeamento(
            id_integracao_endpoint=ep.id,
            items_root_path=m.items_root_path,
            external_id_mode=m.external_id_mode,
            external_id_path=m.external_id_path,
            external_id_composite_paths=m.external_id_composite_paths,
            external_id_composite_template=m.external_id_composite_template,
            campo_titulo=m.campo_titulo,
            campo_descricao=m.campo_descricao,
            campo_codigo=m.campo_codigo,
            campo_data_inicio=m.campo_data_inicio,
            campo_data_fim=m.campo_data_fim,
            campo_data_conclusao=m.campo_data_conclusao,
            campo_status=m.campo_status,
            map_status_values=m.map_status_values,
            campo_progresso=m.campo_progresso,
            campo_valor_inicial=m.campo_valor_inicial,
            campo_valor_pretendido=m.campo_valor_pretendido,
            campo_valor_atual=m.campo_valor_atual,
            campo_responsavel=m.campo_responsavel,
            campo_tipo_anotacao=m.campo_tipo_anotacao,
            campo_meta_id=m.campo_meta_id,
            campo_meta_titulo=m.campo_meta_titulo,
            campo_unidade_origem=m.campo_unidade_origem,
            campo_projeto=m.campo_projeto,
            campo_prioridade=m.campo_prioridade,
            campo_autor=m.campo_autor,
            campo_data_atualizacao=m.campo_data_atualizacao,
            campo_link_externo=m.campo_link_externo,
            campos_extras=m.campos_extras,
            map_unidades_values=[u.model_dump(mode='json') for u in m.map_unidades_values] if m.map_unidades_values else None,
            map_usuarios_values=[usr.model_dump(mode='json') for usr in m.map_usuarios_values] if m.map_usuarios_values else None,
            regras_de_para=[r.model_dump(mode='json') for r in m.regras_de_para] if m.regras_de_para else [],
            default_id_meta=m.default_id_meta,
            default_id_unidade=m.default_id_unidade,
            regras_transformacao=m.regras_transformacao,
            inativo=False,
            ativo=True,
        )
        db.add(map_obj)

    db.commit()
    db.refresh(ep)
    return _format_endpoint_response(ep, db)


def update_endpoint(db: Session, id_organizacao: UUID, endpoint_id: UUID, data: IntegracaoEndpointUpdate) -> IntegracaoEndpointResponse:
    ep = db.query(IntegracaoEndpoint).join(
        IntegracaoConfig, IntegracaoConfig.id == IntegracaoEndpoint.id_integracao_config
    ).filter(
        IntegracaoEndpoint.id == endpoint_id,
        IntegracaoConfig.id_organizacao == id_organizacao,
        IntegracaoEndpoint.inativo == False,
        IntegracaoConfig.inativo == False
    ).first()

    if not ep:
        raise HTTPException(status_code=404, detail="integration.endpoint_not_found")

    if data.nome is not None:
        ep.nome = data.nome
    if data.tipo_integracao is not None:
        ep.tipo_integracao = data.tipo_integracao
    if data.path is not None:
        ep.path = data.path
    if data.metodo_http is not None:
        ep.metodo_http = data.metodo_http
    if data.modo_execucao is not None:
        ep.modo_execucao = data.modo_execucao
    if data.parametros_config is not None:
        ep.parametros_config = [p.model_dump(mode='json') for p in data.parametros_config]
    if data.headers_custom is not None:
        ep.headers_custom = data.headers_custom
    if data.corpo_requisicao is not None:
        ep.corpo_requisicao = data.corpo_requisicao
    if data.escopo_unidades is not None:
        ep.escopo_unidades = data.escopo_unidades
    if data.unidades_selecionadas is not None:
        ep.unidades_selecionadas = [str(u) for u in data.unidades_selecionadas]
    if data.escopo_usuarios is not None:
        ep.escopo_usuarios = data.escopo_usuarios
    if data.usuarios_selecionados is not None:
        ep.usuarios_selecionados = [str(usr) for usr in data.usuarios_selecionados]
    if data.ativo_sincronizacao is not None:
        ep.ativo_sincronizacao = data.ativo_sincronizacao
    if data.frequencia_cron is not None:
        ep.frequencia_cron = data.frequencia_cron
    if data.funcionalidades_habilitadas is not None:
        ep.funcionalidades_habilitadas = data.funcionalidades_habilitadas

    # Update mapping
    if data.mapeamento:
        m = data.mapeamento
        map_obj = ep.mapeamento
        if not map_obj:
            map_obj = IntegracaoMapeamento(id_integracao_endpoint=ep.id, campo_titulo="Título", inativo=False, ativo=True)
            db.add(map_obj)

        if m.items_root_path is not None:
            map_obj.items_root_path = m.items_root_path
        if m.external_id_mode is not None:
            map_obj.external_id_mode = m.external_id_mode
        if m.external_id_path is not None:
            map_obj.external_id_path = m.external_id_path
        if m.external_id_composite_paths is not None:
            map_obj.external_id_composite_paths = m.external_id_composite_paths
        if m.external_id_composite_template is not None:
            map_obj.external_id_composite_template = m.external_id_composite_template
        if m.campo_titulo is not None:
            map_obj.campo_titulo = m.campo_titulo
        if m.campo_descricao is not None:
            map_obj.campo_descricao = m.campo_descricao
        if m.campo_codigo is not None:
            map_obj.campo_codigo = m.campo_codigo
        if m.campo_data_inicio is not None:
            map_obj.campo_data_inicio = m.campo_data_inicio
        if m.campo_data_fim is not None:
            map_obj.campo_data_fim = m.campo_data_fim
        if m.campo_data_conclusao is not None:
            map_obj.campo_data_conclusao = m.campo_data_conclusao
        if m.campo_status is not None:
            map_obj.campo_status = m.campo_status
        if m.map_status_values is not None:
            map_obj.map_status_values = m.map_status_values
        if m.campo_progresso is not None:
            map_obj.campo_progresso = m.campo_progresso
        if m.campo_valor_inicial is not None:
            map_obj.campo_valor_inicial = m.campo_valor_inicial
        if m.campo_valor_pretendido is not None:
            map_obj.campo_valor_pretendido = m.campo_valor_pretendido
        if m.campo_valor_atual is not None:
            map_obj.campo_valor_atual = m.campo_valor_atual
        if m.campo_responsavel is not None:
            map_obj.campo_responsavel = m.campo_responsavel
        if m.campo_tipo_anotacao is not None:
            map_obj.campo_tipo_anotacao = m.campo_tipo_anotacao
        if m.campo_meta_id is not None:
            map_obj.campo_meta_id = m.campo_meta_id
        if m.campo_meta_titulo is not None:
            map_obj.campo_meta_titulo = m.campo_meta_titulo
        if m.campo_unidade_origem is not None:
            map_obj.campo_unidade_origem = m.campo_unidade_origem
        if m.campo_projeto is not None:
            map_obj.campo_projeto = m.campo_projeto
        if m.campo_prioridade is not None:
            map_obj.campo_prioridade = m.campo_prioridade
        if m.campo_autor is not None:
            map_obj.campo_autor = m.campo_autor
        if m.campo_data_atualizacao is not None:
            map_obj.campo_data_atualizacao = m.campo_data_atualizacao
        if m.campo_link_externo is not None:
            map_obj.campo_link_externo = m.campo_link_externo
        if m.campos_extras is not None:
            map_obj.campos_extras = m.campos_extras
        if m.map_unidades_values is not None:
            map_obj.map_unidades_values = [u.model_dump(mode='json') for u in m.map_unidades_values]
        if m.map_usuarios_values is not None:
            map_obj.map_usuarios_values = [usr.model_dump(mode='json') for usr in m.map_usuarios_values]
        if m.regras_de_para is not None:
            map_obj.regras_de_para = [r.model_dump(mode='json') for r in m.regras_de_para]

        if m.default_id_meta is not None:
            map_obj.default_id_meta = m.default_id_meta
        if m.default_id_unidade is not None:
            map_obj.default_id_unidade = m.default_id_unidade
        if m.regras_transformacao is not None:
            map_obj.regras_transformacao = m.regras_transformacao

        map_obj.updated_at = now_in_app_timezone()

    ep.updated_at = now_in_app_timezone()
    db.commit()
    db.refresh(ep)
    return _format_endpoint_response(ep, db)


def delete_endpoint(db: Session, id_organizacao: UUID, endpoint_id: UUID) -> None:
    ep = db.query(IntegracaoEndpoint).join(
        IntegracaoConfig, IntegracaoConfig.id == IntegracaoEndpoint.id_integracao_config
    ).filter(
        IntegracaoEndpoint.id == endpoint_id,
        IntegracaoConfig.id_organizacao == id_organizacao,
        IntegracaoEndpoint.inativo == False,
        IntegracaoConfig.inativo == False
    ).first()

    if not ep:
        raise HTTPException(status_code=404, detail="integration.endpoint_not_found")

    ep.inativo = True
    ep.ativo = False
    ep.updated_at = now_in_app_timezone()
    if ep.mapeamento:
        ep.mapeamento.inativo = True
        ep.mapeamento.ativo = False
    db.commit()


# ==========================================
# HISTÓRICO DE EXECUÇÕES
# ==========================================

def list_historico_execucoes(
    db: Session,
    id_organizacao: UUID,
    integracao_id: UUID,
    endpoint_id: UUID | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[IntegracaoExecucaoHistoricoResponse]:
    cfg = db.query(IntegracaoConfig).filter(
        IntegracaoConfig.id == integracao_id,
        IntegracaoConfig.id_organizacao == id_organizacao,
        IntegracaoConfig.inativo == False
    ).first()

    if not cfg:
        raise HTTPException(status_code=404, detail="integration.not_found")

    query = db.query(IntegracaoExecucaoHistorico).filter(
        IntegracaoExecucaoHistorico.id_integracao_config == cfg.id,
        IntegracaoExecucaoHistorico.inativo == False
    )

    if endpoint_id:
        query = query.filter(IntegracaoExecucaoHistorico.id_integracao_endpoint == endpoint_id)

    historicos = query.order_by(desc(IntegracaoExecucaoHistorico.data_inicio)).offset(skip).limit(limit).all()

    result = []
    for h in historicos:
        exec_nome = h.usuario_executor.nome if h.usuario_executor else None
        ep_nome = h.endpoint.nome if h.endpoint else None
        result.append(IntegracaoExecucaoHistoricoResponse(
            id=h.id,
            id_integracao_config=h.id_integracao_config,
            id_integracao_endpoint=h.id_integracao_endpoint,
            endpoint_nome=ep_nome,
            data_inicio=h.data_inicio,
            data_fim=h.data_fim,
            status=h.status,
            total_encontrados=h.total_encontrados,
            total_criados=h.total_criados,
            total_atualizados=h.total_atualizados,
            total_inalterados=h.total_inalterados,
            total_erros=h.total_erros,
            log_detalhes=h.log_detalhes,
            disparado_por=h.disparado_por,
            id_usuario_executor=h.id_usuario_executor,
            usuario_executor_nome=exec_nome,
            created_at=h.created_at,
        ))

    return result
