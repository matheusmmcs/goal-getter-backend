import time
import logging
from uuid import UUID
from datetime import datetime, date
from typing import Any, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.timezone import now_in_app_timezone
from app.models.enums import (
    StatusExecucaoEnum,
    OrigemDisparoEnum,
    OrigemEntregaEnum,
    OrigemPlanejamentoEnum,
    TipoIntegracaoEnum,
    ModoExecucaoEnum,
    ParametroTipoOrigemEnum,
    EntregaStatusEnum,
    MetaStatusEnum,
)
from app.models.integracao_config import IntegracaoConfig
from app.models.integracao_endpoint import IntegracaoEndpoint
from app.models.integracao_mapeamento import IntegracaoMapeamento
from app.models.integracao_execucao_historico import IntegracaoExecucaoHistorico
from app.models.entrega import Entrega
from app.models.meta import Meta
from app.models.unidade import Unidade
from app.models.usuario import Usuario
from app.models.usuario_organizacao import UsuarioOrganizacao
from app.schemas.integracao import (
    ParametroConfigSchema,
    SyncPreviewItem,
    SyncPreviewErrorDetail,
    SyncPreviewResponse,
)

from app.services.schema_inspector_service import (
    execute_integrated_request,
    extract_items_by_path,
    extract_field_value,
    build_composite_key,
    parse_date_safe,
    parse_float_safe,
    parse_percent_safe,
)

logger = logging.getLogger(__name__)


def map_status_to_entrega_enum(raw_status: str | None, map_dict: dict[str, str] | None) -> EntregaStatusEnum:
    """Maps external status string to EntregaStatusEnum."""
    if not raw_status:
        return EntregaStatusEnum.NAO_INICIADA
    clean = str(raw_status).strip()
    if map_dict and clean in map_dict:
        target = map_dict[clean]
        try:
            return EntregaStatusEnum(target)
        except Exception:
            pass
    try:
        return EntregaStatusEnum(clean)
    except Exception:
        pass
    upper = clean.upper()
    if any(k in upper for k in ('CONCLU', 'ENTREG', 'DONE', 'RESOLV', 'CLOSE', 'FINISH')):
        return EntregaStatusEnum.ENTREGUE
    if any(k in upper for k in ('ANDAMENT', 'PROGRESS', 'DOING', 'OPEN', 'ACTIVE')):
        return EntregaStatusEnum.EM_ANDAMENTO
    if any(k in upper for k in ('CANCEL', 'ABORT', 'REJECT')):
        return EntregaStatusEnum.CANCELADA
    if any(k in upper for k in ('ATRAS', 'DELAY', 'LATE')):
        return EntregaStatusEnum.ATRASADA
    return EntregaStatusEnum.NAO_INICIADA


def map_status_to_meta_enum(raw_status: str | None, map_dict: dict[str, str] | None) -> MetaStatusEnum:
    """Maps external status string to MetaStatusEnum."""
    if not raw_status:
        return MetaStatusEnum.PLANEJADA
    clean = str(raw_status).strip()
    if map_dict and clean in map_dict:
        target = map_dict[clean]
        try:
            return MetaStatusEnum(target)
        except Exception:
            pass
    try:
        return MetaStatusEnum(clean)
    except Exception:
        pass
    upper = clean.upper()
    if any(k in upper for k in ('CONCLU', 'DONE', 'CLOSE', 'FINISH')):
        return MetaStatusEnum.CONCLUIDA
    if any(k in upper for k in ('ANDAMENT', 'PROGRESS', 'DOING', 'OPEN', 'ACTIVE')):
        return MetaStatusEnum.EM_ANDAMENTO
    if any(k in upper for k in ('CANCEL', 'ABORT')):
        return MetaStatusEnum.CANCELADA
    return MetaStatusEnum.PLANEJADA


async def run_endpoint_sync(
    db: Session,
    endpoint_id: UUID,
    disparo: OrigemDisparoEnum = OrigemDisparoEnum.MANUAL,
    id_usuario_executor: UUID | None = None
) -> IntegracaoExecucaoHistorico:
    """Executes synchronization pipeline for a specific IntegracaoEndpoint."""
    endpoint = db.query(IntegracaoEndpoint).filter(
        IntegracaoEndpoint.id == endpoint_id,
        IntegracaoEndpoint.inativo == False
    ).first()

    if not endpoint:
        raise HTTPException(status_code=404, detail="integration.endpoint_not_found")

    integracao = db.query(IntegracaoConfig).filter(
        IntegracaoConfig.id == endpoint.id_integracao_config,
        IntegracaoConfig.inativo == False
    ).first()

    if not integracao:
        raise HTTPException(status_code=404, detail="integration.not_found")

    mapeamento = db.query(IntegracaoMapeamento).filter(
        IntegracaoMapeamento.id_integracao_endpoint == endpoint.id,
        IntegracaoMapeamento.inativo == False
    ).first()

    if not mapeamento:
        raise HTTPException(status_code=400, detail="integration.mapping_required")

    start_dt = now_in_app_timezone()
    historico = IntegracaoExecucaoHistorico(
        id_integracao_config=integracao.id,
        id_integracao_endpoint=endpoint.id,
        data_inicio=start_dt,
        status=StatusExecucaoEnum.EM_ANDAMENTO,
        disparado_por=disparo,
        id_usuario_executor=id_usuario_executor,
    )
    db.add(historico)
    db.commit()
    db.refresh(historico)

    total_encontrados = 0
    total_criados = 0
    total_atualizados = 0
    total_inalterados = 0
    total_erros = 0
    item_logs: list[dict[str, Any]] = []

    try:
        # Build De-Para Lookup Dictionaries
        unit_depara: dict[str, UUID | None] = {}
        if mapeamento.map_unidades_values:
            for u in mapeamento.map_unidades_values:
                if isinstance(u, dict):
                    code = str(u.get("codigo_externo", "")).strip().upper()
                    raw_uid = u.get("id_unidade")
                    unit_depara[code] = UUID(raw_uid) if raw_uid else None

        user_depara: dict[str, UUID] = {}
        if mapeamento.map_usuarios_values:
            for usr in mapeamento.map_usuarios_values:
                if isinstance(usr, dict):
                    ident = str(usr.get("identificador_externo", "")).strip().lower()
                    raw_usrid = usr.get("id_usuario")
                    if raw_usrid:
                        user_depara[ident] = UUID(raw_usrid)

        # Pre-fetch organization users for fallback match (by CPF, email, login)
        org_users = db.query(Usuario).join(
            UsuarioOrganizacao, UsuarioOrganizacao.id_usuario == Usuario.id
        ).filter(
            UsuarioOrganizacao.id_organizacao == integracao.id_organizacao,
            UsuarioOrganizacao.inativo == False,
            Usuario.inativo == False
        ).all()

        user_by_cpf = {u.cpf.replace('.', '').replace('-', '').strip(): u.id for u in org_users if u.cpf}
        user_by_email = {u.email.strip().lower(): u.id for u in org_users if u.email}
        user_by_login = {u.usuario.strip().lower(): u.id for u in org_users if u.usuario}

        # Convert endpoint parameters to models
        params_objs = []
        if endpoint.parametros_config:
            for p in endpoint.parametros_config:
                if isinstance(p, dict):
                    params_objs.append(ParametroConfigSchema(**p))
                elif isinstance(p, ParametroConfigSchema):
                    params_objs.append(p)

        # 1. Determine execution iterations (Dynamic Unit, Dynamic User, or Global Single)
        has_dynamic_unit = any(
            (getattr(p, "tipo_origem", None) == ParametroTipoOrigemEnum.DINAMICO_UNIDADE or
             any(t in (p.valor_template or "") for t in ("{codigo_unidade}", "{sigla_unidade}", "{id_unidade}")))
            for p in params_objs
        ) or any(t in (endpoint.path or "") for t in ("{codigo_unidade}", "{sigla_unidade}", "{id_unidade}"))

        has_dynamic_user = any(
            (getattr(p, "tipo_origem", None) == ParametroTipoOrigemEnum.DINAMICO_USUARIO or
             "{usuario_" in (p.valor_template or "") or "{id_usuario}" in (p.valor_template or ""))
            for p in params_objs
        ) or any(t in (endpoint.path or "") for t in ("{usuario_", "{id_usuario}"))

        iteration_contexts: list[dict[str, Any]] = []

        if has_dynamic_unit:
            unit_query = db.query(Unidade).filter(
                Unidade.id_organizacao == integracao.id_organizacao,
                Unidade.inativo == False
            )
            if endpoint.escopo_unidades == "SELECIONADAS" and endpoint.unidades_selecionadas:
                unit_query = unit_query.filter(Unidade.id.in_(endpoint.unidades_selecionadas))
            
            units = unit_query.all()
            for u in units:
                iteration_contexts.append({
                    "id_organizacao": str(integracao.id_organizacao),
                    "id_unidade": str(u.id),
                    "codigo_unidade": u.sigla or str(u.id),
                    "unidade_id": u.sigla or str(u.id),
                    "sigla_unidade": u.sigla or u.nome,
                    "nome_unidade": u.nome,
                })

        elif has_dynamic_user:
            user_query = db.query(Usuario).join(
                UsuarioOrganizacao, UsuarioOrganizacao.id_usuario == Usuario.id
            ).filter(
                UsuarioOrganizacao.id_organizacao == integracao.id_organizacao,
                UsuarioOrganizacao.inativo == False,
                Usuario.inativo == False
            )
            if endpoint.escopo_usuarios == "SELECIONADOS" and endpoint.usuarios_selecionados:
                user_query = user_query.filter(Usuario.id.in_(endpoint.usuarios_selecionados))
            
            users = user_query.all()
            for u in users:
                clean_cpf = u.cpf.replace('.', '').replace('-', '').strip() if u.cpf else ""
                iteration_contexts.append({
                    "id_organizacao": str(integracao.id_organizacao),
                    "id_usuario": str(u.id),
                    "usuario_cpf": clean_cpf,
                    "cpf_usuario": clean_cpf,
                    "usuario_email": u.email or "",
                    "usuario_login": u.usuario or u.email or "",
                })

        else:
            iteration_contexts.append({"id_organizacao": str(integracao.id_organizacao)})

        # 2. Execute requests and extract items
        raw_items_with_context: list[Tuple[dict[str, Any], dict[str, Any]]] = []

        for ctx in iteration_contexts:
            status_code, _, payload, _, _ = await execute_integrated_request(
                url_base=integracao.url_base,
                path=endpoint.path,
                metodo_http=endpoint.metodo_http,
                tipo_autenticacao=integracao.tipo_autenticacao,
                auth_endpoint_path=integracao.auth_endpoint_path,
                auth_metodo_http=integracao.auth_metodo_http,
                auth_headers=integracao.auth_headers,
                auth_payload=integracao.auth_payload,
                auth_token_path=integracao.auth_token_path,
                auth_static_config=integracao.auth_static_config,
                headers_padrao=integracao.headers_padrao,
                headers_custom=endpoint.headers_custom,
                parametros_config=params_objs,
                corpo_requisicao=endpoint.corpo_requisicao,
                context=ctx,
            )

            if not (200 <= status_code < 300):
                item_logs.append({
                    "context": ctx,
                    "error": f"Requisição falhou com status {status_code}: {str(payload)[:200]}"
                })
                total_erros += 1
                continue

            extracted = extract_items_by_path(payload, mapeamento.items_root_path)
            for itm in extracted:
                if isinstance(itm, dict):
                    raw_items_with_context.append((itm, ctx))

        total_encontrados = len(raw_items_with_context)

        # 3. Transform and Upsert according to tipo_integracao
        if endpoint.tipo_integracao == TipoIntegracaoEnum.RECEBER_METAS:
            for item, ctx in raw_items_with_context:
                ext_id = "unknown"
                try:
                    if mapeamento.external_id_mode == "COMPOSITE":
                        ext_id = build_composite_key(item, mapeamento.external_id_composite_template, mapeamento.external_id_composite_paths)
                    else:
                        ext_id = str(extract_field_value(item, mapeamento.external_id_path or "id") or "")

                    if not ext_id:
                        total_erros += 1
                        continue

                    titulo = str(extract_field_value(item, mapeamento.campo_titulo) or "Meta Sem Título")
                    descricao = extract_field_value(item, mapeamento.campo_descricao)
                    descricao = str(descricao) if descricao is not None else None
                    codigo = str(extract_field_value(item, mapeamento.campo_codigo)) if mapeamento.campo_codigo else None

                    dt_ini = parse_date_safe(extract_field_value(item, mapeamento.campo_data_inicio))
                    dt_fim = parse_date_safe(extract_field_value(item, mapeamento.campo_data_fim))

                    raw_status = str(extract_field_value(item, mapeamento.campo_status) or "")
                    meta_status = map_status_to_meta_enum(raw_status, mapeamento.map_status_values)

                    val_ini = parse_float_safe(extract_field_value(item, mapeamento.campo_valor_inicial))
                    val_pret = parse_float_safe(extract_field_value(item, mapeamento.campo_valor_pretendido))
                    val_atual = parse_float_safe(extract_field_value(item, mapeamento.campo_valor_atual))

                    # Resolve Unit
                    target_unit_id = None
                    raw_unit_code = extract_field_value(item, mapeamento.campo_unidade_origem)
                    if raw_unit_code:
                        target_unit_id = unit_depara.get(str(raw_unit_code).strip().upper())
                    if not target_unit_id and ctx.get("id_unidade"):
                        try:
                            target_unit_id = UUID(ctx["id_unidade"])
                        except Exception:
                            pass
                    if not target_unit_id:
                        target_unit_id = mapeamento.default_id_unidade

                    # Upsert Meta
                    existing_meta = db.query(Meta).filter(
                        Meta.id_integracao_config == integracao.id,
                        Meta.external_id == ext_id,
                        Meta.inativo == False
                    ).first()

                    if existing_meta:
                        changed = False
                        if existing_meta.titulo != titulo:
                            existing_meta.titulo = titulo
                            changed = True
                        if existing_meta.descricao != descricao:
                            existing_meta.descricao = descricao
                            changed = True
                        if codigo and existing_meta.codigo != codigo:
                            existing_meta.codigo = codigo
                            changed = True
                        if existing_meta.data_inicio != dt_ini:
                            existing_meta.data_inicio = dt_ini
                            changed = True
                        if existing_meta.data_fim != dt_fim:
                            existing_meta.data_fim = dt_fim
                            changed = True
                        if existing_meta.status != meta_status:
                            existing_meta.status = meta_status
                            changed = True
                        if float(existing_meta.valor_meta_inicial or 0) != val_ini:
                            existing_meta.valor_meta_inicial = val_ini
                            changed = True
                        if float(existing_meta.valor_meta_pretendida or 0) != val_pret:
                            existing_meta.valor_meta_pretendida = val_pret
                            changed = True
                        if float(existing_meta.valor_meta_atual or 0) != val_atual:
                            existing_meta.valor_meta_atual = val_atual
                            changed = True
                        if existing_meta.id_unidade != target_unit_id:
                            existing_meta.id_unidade = target_unit_id
                            changed = True

                        if changed:
                            existing_meta.updated_at = now_in_app_timezone()
                            existing_meta.external_data = item
                            total_atualizados += 1
                        else:
                            total_inalterados += 1
                    else:
                        new_meta = Meta(
                            id_organizacao=integracao.id_organizacao,
                            id_unidade=target_unit_id,
                            id_integracao_config=integracao.id,
                            id_integracao_endpoint=endpoint.id,
                            external_id=ext_id,
                            titulo=titulo,
                            descricao=descricao,
                            codigo=codigo,
                            valor_meta_inicial=val_ini,
                            valor_meta_pretendida=val_pret,
                            valor_meta_atual=val_atual,
                            data_inicio=dt_ini,
                            data_fim=dt_fim,
                            status=meta_status,
                            tipo_origem=OrigemPlanejamentoEnum.EXTERNA,
                            external_data=item,
                            inativo=False,
                            ativo=True,
                        )
                        db.add(new_meta)
                        total_criados += 1
                except Exception as e:
                    total_erros += 1
                    item_logs.append({"item_id": ext_id, "error": str(e)})

        elif endpoint.tipo_integracao == TipoIntegracaoEnum.RECEBER_ENTREGAS:
            for item, ctx in raw_items_with_context:
                ext_id = "unknown"
                try:
                    if mapeamento.external_id_mode == "COMPOSITE":
                        ext_id = build_composite_key(item, mapeamento.external_id_composite_template, mapeamento.external_id_composite_paths)
                    else:
                        ext_id = str(extract_field_value(item, mapeamento.external_id_path or "id") or "")

                    if not ext_id:
                        total_erros += 1
                        continue

                    titulo = str(extract_field_value(item, mapeamento.campo_titulo) or "Entrega Sem Título")
                    descricao = extract_field_value(item, mapeamento.campo_descricao)
                    descricao = str(descricao) if descricao is not None else None

                    dt_ini = parse_date_safe(extract_field_value(item, mapeamento.campo_data_inicio))
                    dt_fim = parse_date_safe(extract_field_value(item, mapeamento.campo_data_fim))
                    dt_conc = parse_date_safe(extract_field_value(item, mapeamento.campo_data_conclusao))

                    raw_status = str(extract_field_value(item, mapeamento.campo_status) or "")
                    entrega_status = map_status_to_entrega_enum(raw_status, mapeamento.map_status_values)
                    progresso = parse_percent_safe(extract_field_value(item, mapeamento.campo_progresso))

                    # Resolve Unit
                    target_unit_id = None
                    raw_unit_code = extract_field_value(item, mapeamento.campo_unidade_origem)
                    if raw_unit_code:
                        target_unit_id = unit_depara.get(str(raw_unit_code).strip().upper())
                    if not target_unit_id and ctx.get("id_unidade"):
                        try:
                            target_unit_id = UUID(ctx["id_unidade"])
                        except Exception:
                            pass
                    if not target_unit_id:
                        target_unit_id = mapeamento.default_id_unidade

                    # Resolve Responsible User
                    target_user_id = None
                    resp_val = extract_field_value(item, mapeamento.campo_responsavel)
                    if resp_val:
                        resp_str = str(resp_val).strip()
                        # Check De-Para first
                        target_user_id = user_depara.get(resp_str.lower())
                        if not target_user_id:
                            # Try CPF
                            clean_cpf = resp_str.replace('.', '').replace('-', '')
                            target_user_id = user_by_cpf.get(clean_cpf) or user_by_email.get(resp_str.lower()) or user_by_login.get(resp_str.lower())

                    if not target_user_id and ctx.get("id_usuario"):
                        try:
                            target_user_id = UUID(ctx["id_usuario"])
                        except Exception:
                            pass

                    # Resolve Goal (Meta)
                    target_meta_id = mapeamento.default_id_meta

                    # Upsert Entrega
                    existing_entrega = db.query(Entrega).filter(
                        Entrega.id_integracao_config == integracao.id,
                        Entrega.external_id == ext_id,
                        Entrega.inativo == False
                    ).first()

                    if existing_entrega:
                        changed = False
                        if existing_entrega.titulo != titulo:
                            existing_entrega.titulo = titulo
                            changed = True
                        if existing_entrega.descricao != descricao:
                            existing_entrega.descricao = descricao
                            changed = True
                        if existing_entrega.data_inicio != dt_ini:
                            existing_entrega.data_inicio = dt_ini
                            changed = True
                        if existing_entrega.data_fim != dt_fim:
                            existing_entrega.data_fim = dt_fim
                            changed = True
                        if existing_entrega.data_conclusao != dt_conc:
                            existing_entrega.data_conclusao = dt_conc
                            changed = True
                        if existing_entrega.status != entrega_status:
                            existing_entrega.status = entrega_status
                            changed = True
                        if existing_entrega.progresso_percentual != progresso:
                            existing_entrega.progresso_percentual = progresso
                            changed = True
                        if existing_entrega.id_unidade != target_unit_id:
                            existing_entrega.id_unidade = target_unit_id
                            changed = True
                        if target_user_id and existing_entrega.id_usuario_responsavel != target_user_id:
                            existing_entrega.id_usuario_responsavel = target_user_id
                            changed = True

                        if changed:
                            existing_entrega.updated_at = now_in_app_timezone()
                            existing_entrega.external_data = item
                            total_atualizados += 1
                        else:
                            total_inalterados += 1
                    else:
                        new_entrega = Entrega(
                            id_organizacao=integracao.id_organizacao,
                            id_meta=target_meta_id,
                            id_unidade=target_unit_id,
                            id_usuario_responsavel=target_user_id,
                            id_integracao_config=integracao.id,
                            id_integracao_endpoint=endpoint.id,
                            external_id=ext_id,
                            titulo=titulo,
                            descricao=descricao,
                            tipo_origem=OrigemEntregaEnum.EXTERNA,
                            data_inicio=dt_ini,
                            data_fim=dt_fim,
                            data_conclusao=dt_conc,
                            status=entrega_status,
                            progresso_percentual=progresso,
                            external_data=item,
                            inativo=False,
                            ativo=True,
                        )
                        db.add(new_entrega)
                        total_criados += 1
                except Exception as e:
                    total_erros += 1
                    item_logs.append({"item_id": ext_id if 'ext_id' in locals() else "unknown", "error": str(e)})

        elif endpoint.tipo_integracao == TipoIntegracaoEnum.RECEBER_TAREFAS:
            # Future support for Daily Stand-up external tasks
            total_criados = len(raw_items_with_context)

        db.commit()

        # Finalize Execution History
        end_dt = now_in_app_timezone()
        historico.data_fim = end_dt
        historico.total_encontrados = total_encontrados
        historico.total_criados = total_criados
        historico.total_atualizados = total_atualizados
        historico.total_inalterados = total_inalterados
        historico.total_erros = total_erros
        historico.log_detalhes = {
            "endpoint_nome": endpoint.nome,
            "tipo_integracao": endpoint.tipo_integracao.value,
            "errors": item_logs[:50]
        }
        historico.status = StatusExecucaoEnum.SUCESSO if total_erros == 0 else (StatusExecucaoEnum.PARCIAL if (total_criados + total_atualizados) > 0 else StatusExecucaoEnum.FALHA)

        db.commit()
        db.refresh(historico)
        return historico

    except Exception as e:
        db.rollback()
        logger.error(f"Erro fatal na sincronização do endpoint {endpoint_id}: {str(e)}", exc_info=True)
        historico.data_fim = now_in_app_timezone()
        historico.status = StatusExecucaoEnum.FALHA
        historico.log_detalhes = {"fatal_error": str(e)}
        db.commit()
        db.refresh(historico)
        return historico


async def run_integration_sync(
    db: Session,
    integracao_id: UUID,
    disparo: OrigemDisparoEnum = OrigemDisparoEnum.MANUAL,
    id_usuario_executor: UUID | None = None
) -> list[IntegracaoExecucaoHistorico]:
    """Executes synchronization for all active endpoints belonging to an IntegracaoConfig."""
    integracao = db.query(IntegracaoConfig).filter(
        IntegracaoConfig.id == integracao_id,
        IntegracaoConfig.inativo == False
    ).first()

    if not integracao:
        raise HTTPException(status_code=404, detail="integration.not_found")

    active_endpoints = db.query(IntegracaoEndpoint).filter(
        IntegracaoEndpoint.id_integracao_config == integracao.id,
        IntegracaoEndpoint.ativo_sincronizacao == True,
        IntegracaoEndpoint.inativo == False
    ).all()

    if not active_endpoints:
        raise HTTPException(status_code=400, detail="integration.no_active_endpoints")

    results = []
    for ep in active_endpoints:
        hist = await run_endpoint_sync(
            db=db,
            endpoint_id=ep.id,
            disparo=disparo,
            id_usuario_executor=id_usuario_executor
        )
        results.append(hist)

    return results


async def preview_endpoint_sync(
    db: Session,
    endpoint_id: UUID
) -> SyncPreviewResponse:
    """Executes a dry-run preview simulation of endpoint synchronization without committing to DB."""
    endpoint = db.query(IntegracaoEndpoint).filter(
        IntegracaoEndpoint.id == endpoint_id,
        IntegracaoEndpoint.inativo == False
    ).first()

    if not endpoint:
        raise HTTPException(status_code=404, detail="integration.endpoint_not_found")

    integracao = db.query(IntegracaoConfig).filter(
        IntegracaoConfig.id == endpoint.id_integracao_config,
        IntegracaoConfig.inativo == False
    ).first()

    if not integracao:
        raise HTTPException(status_code=404, detail="integration.not_found")

    mapeamento = endpoint.mapeamento
    if not mapeamento or mapeamento.inativo:
        raise HTTPException(status_code=400, detail="integration.mapping_not_configured")

    # Build De-Para Lookups
    unit_depara: dict[str, UUID | None] = {}
    if mapeamento.map_unidades_values:
        for u in mapeamento.map_unidades_values:
            if isinstance(u, dict):
                code = str(u.get("codigo_externo", "")).strip().upper()
                raw_uid = u.get("id_unidade")
                unit_depara[code] = UUID(raw_uid) if raw_uid else None

    user_depara: dict[str, UUID] = {}
    if mapeamento.map_usuarios_values:
        for usr in mapeamento.map_usuarios_values:
            if isinstance(usr, dict):
                ident = str(usr.get("identificador_externo", "")).strip().lower()
                raw_usrid = usr.get("id_usuario")
                if raw_usrid:
                    user_depara[ident] = UUID(raw_usrid)

    org_users = db.query(Usuario).join(
        UsuarioOrganizacao, UsuarioOrganizacao.id_usuario == Usuario.id
    ).filter(
        UsuarioOrganizacao.id_organizacao == integracao.id_organizacao,
        UsuarioOrganizacao.inativo == False,
        Usuario.inativo == False
    ).all()

    user_by_cpf = {u.cpf.replace('.', '').replace('-', '').strip(): u for u in org_users if u.cpf}
    user_by_email = {u.email.strip().lower(): u for u in org_users if u.email}
    user_by_login = {u.usuario.strip().lower(): u for u in org_users if u.usuario}
    user_by_id = {u.id: u for u in org_users}

    org_units = db.query(Unidade).filter(
        Unidade.id_organizacao == integracao.id_organizacao,
        Unidade.inativo == False
    ).all()
    unit_by_id = {u.id: u for u in org_units}

    params_objs = []
    if endpoint.parametros_config:
        for p in endpoint.parametros_config:
            if isinstance(p, dict):
                params_objs.append(ParametroConfigSchema(**p))
            elif isinstance(p, ParametroConfigSchema):
                params_objs.append(p)

    has_dynamic_unit = any(
        (getattr(p, "tipo_origem", None) == ParametroTipoOrigemEnum.DINAMICO_UNIDADE or
         any(t in (p.valor_template or "") for t in ("{codigo_unidade}", "{sigla_unidade}", "{id_unidade}")))
        for p in params_objs
    ) or any(t in (endpoint.path or "") for t in ("{codigo_unidade}", "{sigla_unidade}", "{id_unidade}"))

    has_dynamic_user = any(
        (getattr(p, "tipo_origem", None) == ParametroTipoOrigemEnum.DINAMICO_USUARIO or
         "{usuario_" in (p.valor_template or "") or "{id_usuario}" in (p.valor_template or ""))
        for p in params_objs
    ) or any(t in (endpoint.path or "") for t in ("{usuario_", "{id_usuario}"))

    iteration_contexts: list[dict[str, Any]] = []

    if has_dynamic_unit:
        unit_query = db.query(Unidade).filter(
            Unidade.id_organizacao == integracao.id_organizacao,
            Unidade.inativo == False
        )
        if endpoint.escopo_unidades == "SELECIONADAS" and endpoint.unidades_selecionadas:
            unit_query = unit_query.filter(Unidade.id.in_(endpoint.unidades_selecionadas))
        
        units = unit_query.all()
        for u in units:
            iteration_contexts.append({
                "id_organizacao": str(integracao.id_organizacao),
                "id_unidade": str(u.id),
                "codigo_unidade": u.sigla or str(u.id),
                "unidade_id": u.sigla or str(u.id),
                "sigla_unidade": u.sigla or u.nome,
                "nome_unidade": u.nome,
            })

    elif has_dynamic_user:
        user_query = db.query(Usuario).join(
            UsuarioOrganizacao, UsuarioOrganizacao.id_usuario == Usuario.id
        ).filter(
            UsuarioOrganizacao.id_organizacao == integracao.id_organizacao,
            UsuarioOrganizacao.inativo == False,
            Usuario.inativo == False
        )
        if endpoint.escopo_usuarios == "SELECIONADOS" and endpoint.usuarios_selecionados:
            user_query = user_query.filter(Usuario.id.in_(endpoint.usuarios_selecionados))
        
        users = user_query.all()
        for u in users:
            clean_cpf = u.cpf.replace('.', '').replace('-', '').strip() if u.cpf else ""
            iteration_contexts.append({
                "id_organizacao": str(integracao.id_organizacao),
                "id_usuario": str(u.id),
                "usuario_cpf": clean_cpf,
                "cpf_usuario": clean_cpf,
                "usuario_email": u.email or "",
                "usuario_login": u.usuario or u.email or "",
            })

    else:
        iteration_contexts.append({"id_organizacao": str(integracao.id_organizacao)})

    raw_items_with_context: list[Tuple[dict[str, Any], dict[str, Any]]] = []
    total_erros = 0
    warnings: list[str] = []
    motivos_erros: list[SyncPreviewErrorDetail] = []

    for ctx in iteration_contexts:
        status_code, _, payload, _, _ = await execute_integrated_request(
            url_base=integracao.url_base,
            path=endpoint.path,
            metodo_http=endpoint.metodo_http,
            tipo_autenticacao=integracao.tipo_autenticacao,
            auth_endpoint_path=integracao.auth_endpoint_path,
            auth_metodo_http=integracao.auth_metodo_http,
            auth_headers=integracao.auth_headers,
            auth_payload=integracao.auth_payload,
            auth_token_path=integracao.auth_token_path,
            auth_static_config=integracao.auth_static_config,
            headers_padrao=integracao.headers_padrao,
            headers_custom=endpoint.headers_custom,
            parametros_config=params_objs,
            corpo_requisicao=endpoint.corpo_requisicao,
            context=ctx,
        )

        if not (200 <= status_code < 300):
            ctx_desc = ctx.get("nome_unidade") or ctx.get("sigla_unidade") or ctx.get("usuario_email") or ctx.get("usuario_login") or "Contexto Geral"
            msg = f"Falha na requisição HTTP (Status {status_code}) ao consultar a API para o contexto '{ctx_desc}'."
            warnings.append(msg)
            motivos_erros.append(SyncPreviewErrorDetail(
                tipo="HTTP_ERROR",
                mensagem=msg,
                contexto=ctx,
            ))
            total_erros += 1
            continue

        extracted = extract_items_by_path(payload, mapeamento.items_root_path)
        for itm in extracted:
            if isinstance(itm, dict):
                raw_items_with_context.append((itm, ctx))

    total_encontrados = len(raw_items_with_context)
    total_novos = 0
    total_atualizados = 0
    total_inalterados = 0
    preview_items: list[SyncPreviewItem] = []

    for item, ctx in raw_items_with_context:
        ext_id = None
        if mapeamento.external_id_mode == "COMPOSITE":
            ext_id = build_composite_key(
                item,
                mapeamento.external_id_composite_paths,
                mapeamento.external_id_composite_template or ""
            )
        else:
            val = extract_field_value(item, mapeamento.external_id_path or "id")
            if val is not None:
                ext_id = str(val)

        if not ext_id:
            msg = f"Registro descartado: o identificador único '{mapeamento.external_id_path or 'id'}' não foi localizado no item retornado."
            motivos_erros.append(SyncPreviewErrorDetail(
                tipo="MISSING_ID",
                mensagem=msg,
                contexto=ctx,
                item_raw=item,
            ))
            total_erros += 1
            continue

        titulo = str(extract_field_value(item, mapeamento.campo_titulo) or "Item sem título")

        # Resolve Unit
        target_unit_id = None
        raw_unit_code = extract_field_value(item, mapeamento.campo_unidade_origem)
        if raw_unit_code:
            target_unit_id = unit_depara.get(str(raw_unit_code).strip().upper())
        if not target_unit_id and ctx.get("id_unidade"):
            try:
                target_unit_id = UUID(ctx["id_unidade"])
            except Exception:
                pass
        if not target_unit_id:
            target_unit_id = mapeamento.default_id_unidade

        unit_obj = unit_by_id.get(target_unit_id) if target_unit_id else None
        unit_name = (f"[{unit_obj.sigla}] {unit_obj.nome}" if unit_obj.sigla else unit_obj.nome) if unit_obj else None

        # Resolve User
        target_user_id = None
        resp_val = extract_field_value(item, mapeamento.campo_responsavel)
        if resp_val:
            resp_str = str(resp_val).strip()
            target_user_id = user_depara.get(resp_str.lower())
            if not target_user_id:
                clean_cpf = resp_str.replace('.', '').replace('-', '')
                target_usr = user_by_cpf.get(clean_cpf) or user_by_email.get(resp_str.lower()) or user_by_login.get(resp_str.lower())
                if target_usr:
                    target_user_id = target_usr.id
        if not target_user_id and ctx.get("id_usuario"):
            try:
                target_user_id = UUID(ctx["id_usuario"])
            except Exception:
                pass

        user_obj = user_by_id.get(target_user_id) if target_user_id else None
        user_name = user_obj.nome if user_obj else (str(resp_val) if resp_val else None)

        dt_ini = parse_date_safe(extract_field_value(item, mapeamento.campo_data_inicio))
        dt_fim = parse_date_safe(extract_field_value(item, mapeamento.campo_data_fim))
        raw_status = str(extract_field_value(item, mapeamento.campo_status) or "")
        progresso = parse_percent_safe(extract_field_value(item, mapeamento.campo_progresso))

        acao = "CRIAR"
        if endpoint.tipo_integracao.value == "RECEBER_METAS":
            meta_status = map_status_to_meta_enum(raw_status, mapeamento.map_status_values)
            existing = db.query(Meta).filter(
                Meta.id_integracao_config == integracao.id,
                Meta.external_id == ext_id,
                Meta.inativo == False
            ).first()
            if existing:
                if existing.titulo != titulo or existing.status != meta_status:
                    acao = "ATUALIZAR"
                    total_atualizados += 1
                else:
                    acao = "INALTERADO"
                    total_inalterados += 1
            else:
                total_novos += 1
        else:
            entrega_status = map_status_to_entrega_enum(raw_status, mapeamento.map_status_values)
            existing = db.query(Entrega).filter(
                Entrega.id_integracao_config == integracao.id,
                Entrega.external_id == ext_id,
                Entrega.inativo == False
            ).first()
            if existing:
                if existing.titulo != titulo or existing.status != entrega_status or (target_user_id and existing.id_usuario_responsavel != target_user_id):
                    acao = "ATUALIZAR"
                    total_atualizados += 1
                else:
                    acao = "INALTERADO"
                    total_inalterados += 1
            else:
                total_novos += 1

        if len(preview_items) < 50:
            preview_items.append(SyncPreviewItem(
                external_id=ext_id,
                titulo=titulo,
                tipo_integracao=endpoint.tipo_integracao,
                acao=acao,
                status=raw_status or (entrega_status.value if endpoint.tipo_integracao.value != "RECEBER_METAS" else meta_status.value),
                data_inicio=dt_ini.isoformat() if dt_ini else None,
                data_fim=dt_fim.isoformat() if dt_fim else None,
                usuario_responsavel_nome=user_name,
                unidade_nome=unit_name,
                progresso_percentual=progresso,
            ))

    return SyncPreviewResponse(
        integracao_id=integracao.id,
        integracao_nome=integracao.nome,
        endpoint_id=endpoint.id,
        endpoint_nome=endpoint.nome,
        total_encontrados=total_encontrados,
        total_novos=total_novos,
        total_atualizados=total_atualizados,
        total_inalterados=total_inalterados,
        total_erros=total_erros,
        items=preview_items,
        warnings=warnings,
        motivos_erros=motivos_erros,
    )


async def preview_integration_sync(
    db: Session,
    integracao_id: UUID
) -> SyncPreviewResponse:
    """Aggregates dry-run preview simulation for all active endpoints of an integration."""
    integracao = db.query(IntegracaoConfig).filter(
        IntegracaoConfig.id == integracao_id,
        IntegracaoConfig.inativo == False
    ).first()

    if not integracao:
        raise HTTPException(status_code=404, detail="integration.not_found")

    active_endpoints = db.query(IntegracaoEndpoint).filter(
        IntegracaoEndpoint.id_integracao_config == integracao.id,
        IntegracaoEndpoint.ativo_sincronizacao == True,
        IntegracaoEndpoint.inativo == False
    ).all()

    if not active_endpoints:
        raise HTTPException(status_code=400, detail="integration.no_active_endpoints")

    total_encontrados = 0
    total_novos = 0
    total_atualizados = 0
    total_inalterados = 0
    total_erros = 0
    all_items: list[SyncPreviewItem] = []
    all_warnings: list[str] = []
    all_motivos_erros: list[SyncPreviewErrorDetail] = []

    for ep in active_endpoints:
        try:
            ep_preview = await preview_endpoint_sync(db=db, endpoint_id=ep.id)
            total_encontrados += ep_preview.total_encontrados
            total_novos += ep_preview.total_novos
            total_atualizados += ep_preview.total_atualizados
            total_inalterados += ep_preview.total_inalterados
            total_erros += ep_preview.total_erros
            all_items.extend(ep_preview.items)
            all_warnings.extend(ep_preview.warnings)
            all_motivos_erros.extend(ep_preview.motivos_erros)
        except Exception as ex:
            msg = f"Endpoint '{ep.nome}' falhou na simulação: {str(ex)}"
            all_warnings.append(msg)
            all_motivos_erros.append(SyncPreviewErrorDetail(
                tipo="ENDPOINT_ERROR",
                mensagem=msg,
            ))
            total_erros += 1

    return SyncPreviewResponse(
        integracao_id=integracao.id,
        integracao_nome=integracao.nome,
        total_encontrados=total_encontrados,
        total_novos=total_novos,
        total_atualizados=total_atualizados,
        total_inalterados=total_inalterados,
        total_erros=total_erros,
        items=all_items[:50],
        warnings=all_warnings,
        motivos_erros=all_motivos_erros,
    )


