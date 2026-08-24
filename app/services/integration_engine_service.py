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
    LiveTaskItem,
    LiveTasksResponse,
    EndpointOpcaoItem,
)

from app.services.schema_inspector_service import (
    execute_integrated_request,
    extract_items_by_path,
    extract_field_value,
    resolve_item_url_template,
    build_composite_key,
    parse_date_safe,
    parse_float_safe,
    parse_percent_safe,
)

logger = logging.getLogger(__name__)


def safe_field_str(val: Any) -> str | None:
    """Extracts clean string representation handling None and nested dict objects."""
    if val is None:
        return None
    if isinstance(val, dict):
        return str(val.get("name") or val.get("nome") or val.get("title") or val.get("titulo") or val.get("id") or val)
    return str(val)


def map_status_to_entrega_enum(raw_status: str | None, map_dict: dict[str, str] | None) -> EntregaStatusEnum:
    """Maps external status string to EntregaStatusEnum."""
    if not raw_status:
        return EntregaStatusEnum.NAO_INICIADA
    clean = raw_status.strip()
    if map_dict and isinstance(map_dict, dict) and clean in map_dict:
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
    clean = raw_status.strip()
    if map_dict and isinstance(map_dict, dict) and clean in map_dict:
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
    id_usuario_executor: UUID | None = None,
    selected_external_ids: list[str] | None = None,
    simulated_user_id: UUID | None = None,
    simulated_unit_id: UUID | None = None,
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
        # Build De-Para Lookup Dictionaries from regras_de_para or legacy lists
        unit_depara: dict[str, UUID | None] = {}
        user_depara: dict[str, UUID] = {}
        status_map: dict[str, str] = {}

        if mapeamento.regras_de_para:
            for r in mapeamento.regras_de_para:
                if isinstance(r, dict):
                    tipo = r.get("tipo")
                    for v in (r.get("valores") or []):
                        if isinstance(v, dict):
                            de_val = str(v.get("de", "")).strip()
                            para_val = str(v.get("para", "")).strip()
                            if de_val and para_val:
                                if tipo == "STATUS":
                                    status_map[de_val] = para_val
                                elif tipo == "UNIDADE":
                                    try:
                                        unit_depara[de_val.upper()] = UUID(para_val)
                                    except Exception:
                                        pass
                                elif tipo == "USUARIO":
                                    try:
                                        user_depara[de_val.lower()] = UUID(para_val)
                                    except Exception:
                                        pass

        if not unit_depara and mapeamento.map_unidades_values:
            for u in mapeamento.map_unidades_values:
                if isinstance(u, dict):
                    code = str(u.get("codigo_externo", "")).strip().upper()
                    raw_uid = u.get("id_unidade")
                    unit_depara[code] = UUID(raw_uid) if raw_uid else None

        if not user_depara and mapeamento.map_usuarios_values:
            for usr in mapeamento.map_usuarios_values:
                if isinstance(usr, dict):
                    ident = str(usr.get("identificador_externo", "")).strip().lower()
                    raw_usrid = usr.get("id_usuario")
                    if raw_usrid:
                        user_depara[ident] = UUID(raw_usrid)

        if not status_map and mapeamento.map_status_values:
            status_map = dict(mapeamento.map_status_values or {})

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
             any(t in (p.valor_template or "") for t in ("{codigo_unidade}", "{sigla_unidade}", "{id_unidade}", "{unit.", "{unidade.")))
            for p in params_objs
        ) or any(t in (endpoint.path or "") for t in ("{codigo_unidade}", "{sigla_unidade}", "{id_unidade}", "{unit.", "{unidade."))

        has_dynamic_user = any(
            (getattr(p, "tipo_origem", None) == ParametroTipoOrigemEnum.DINAMICO_USUARIO or
             any(t in (p.valor_template or "") for t in ("{usuario_", "{id_usuario}", "{user.", "{usuario.")))
            for p in params_objs
        ) or any(t in (endpoint.path or "") for t in ("{usuario_", "{id_usuario}", "{user.", "{usuario."))

        iteration_contexts: list[dict[str, Any]] = []

        if has_dynamic_unit:
            unit_query = db.query(Unidade).filter(
                Unidade.id_organizacao == integracao.id_organizacao,
                Unidade.inativo == False
            )
            if simulated_unit_id:
                unit_query = unit_query.filter(Unidade.id == simulated_unit_id)
            elif endpoint.escopo_unidades == "SELECIONADAS" and endpoint.unidades_selecionadas:
                unit_query = unit_query.filter(Unidade.id.in_(endpoint.unidades_selecionadas))
            
            units = unit_query.all()
            for u in units:
                u_ctx = {
                    "id_organizacao": str(integracao.id_organizacao),
                    "id_unidade": str(u.id),
                    "codigo_unidade": u.sigla or str(u.id),
                    "unidade_id": u.sigla or str(u.id),
                    "sigla_unidade": u.sigla or u.nome,
                    "nome_unidade": u.nome,
                }
                if u.campos_customizados and isinstance(u.campos_customizados, dict):
                    for k, v in u.campos_customizados.items():
                        u_ctx[f"unidade_{k}"] = str(v) if v is not None else ""
                        u_ctx[k] = str(v) if v is not None else ""
                iteration_contexts.append(u_ctx)

        elif has_dynamic_user:
            user_rows = db.query(Usuario, UsuarioOrganizacao).join(
                UsuarioOrganizacao, UsuarioOrganizacao.id_usuario == Usuario.id
            ).filter(
                UsuarioOrganizacao.id_organizacao == integracao.id_organizacao,
                UsuarioOrganizacao.inativo == False,
                Usuario.inativo == False
            )
            if simulated_user_id:
                user_rows = user_rows.filter(Usuario.id == simulated_user_id)
            elif endpoint.escopo_usuarios == "USUARIO_LOGADO":
                active_target = id_usuario_executor
                if active_target:
                    user_rows = user_rows.filter(Usuario.id == active_target)
            elif endpoint.escopo_usuarios == "SELECIONADOS" and endpoint.usuarios_selecionados:
                user_rows = user_rows.filter(Usuario.id.in_(endpoint.usuarios_selecionados))
            
            for u, uo in user_rows.all():
                clean_cpf = u.cpf.replace('.', '').replace('-', '').strip() if u.cpf else ""
                usr_ctx = {
                    "id_organizacao": str(integracao.id_organizacao),
                    "id_usuario": str(u.id),
                    "usuario_cpf": clean_cpf,
                    "cpf_usuario": clean_cpf,
                    "usuario_email": u.email or "",
                    "usuario_login": u.usuario or u.email or "",
                }
                if uo.campos_customizados and isinstance(uo.campos_customizados, dict):
                    for k, v in uo.campos_customizados.items():
                        usr_ctx[f"usuario_{k}"] = str(v) if v is not None else ""
                        usr_ctx[k] = str(v) if v is not None else ""
                iteration_contexts.append(usr_ctx)

        else:
            iteration_contexts.append({"id_organizacao": str(integracao.id_organizacao)})

        # 2. Execute requests and extract items
        raw_items_with_context: list[Tuple[dict[str, Any], dict[str, Any]]] = []

        for ctx in iteration_contexts:
            status_code, _, payload, _, _, _ = await execute_integrated_request(
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

        selected_set = {str(sid).strip() for sid in selected_external_ids} if selected_external_ids is not None else None

        # 3. Transform and Upsert according to tipo_integracao
        if endpoint.tipo_integracao == TipoIntegracaoEnum.RECEBER_METAS:
            dedup_metas_raw = []
            seen_meta_ids = set()
            for item, ctx in raw_items_with_context:
                if mapeamento.external_id_mode == "COMPOSITE":
                    e_id = build_composite_key(item, mapeamento.external_id_composite_template, mapeamento.external_id_composite_paths)
                else:
                    e_id = str(extract_field_value(item, mapeamento.external_id_path or "id") or "")
                if e_id not in seen_meta_ids:
                    seen_meta_ids.add(e_id)
                    dedup_metas_raw.append((item, ctx))

            for item, ctx in dedup_metas_raw:
                ext_id = "unknown"
                try:
                    if mapeamento.external_id_mode == "COMPOSITE":
                        ext_id = build_composite_key(item, mapeamento.external_id_composite_template, mapeamento.external_id_composite_paths)
                    else:
                        ext_id = str(extract_field_value(item, mapeamento.external_id_path or "id") or "")

                    if not ext_id:
                        total_erros += 1
                        continue

                    if selected_set is not None and str(ext_id).strip() not in selected_set:
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
                        Meta.id_organizacao == integracao.id_organizacao,
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
            dedup_entregas_raw = []
            seen_entrega_ids = set()
            for item, ctx in raw_items_with_context:
                if mapeamento.external_id_mode == "COMPOSITE":
                    e_id = build_composite_key(item, mapeamento.external_id_composite_template, mapeamento.external_id_composite_paths)
                else:
                    e_id = str(extract_field_value(item, mapeamento.external_id_path or "id") or "")
                if e_id not in seen_entrega_ids:
                    seen_entrega_ids.add(e_id)
                    dedup_entregas_raw.append((item, ctx))

            for item, ctx in dedup_entregas_raw:
                ext_id = "unknown"
                try:
                    if mapeamento.external_id_mode == "COMPOSITE":
                        ext_id = build_composite_key(item, mapeamento.external_id_composite_template, mapeamento.external_id_composite_paths)
                    else:
                        ext_id = str(extract_field_value(item, mapeamento.external_id_path or "id") or "")

                    if not ext_id:
                        total_erros += 1
                        continue

                    if selected_set is not None and str(ext_id).strip() not in selected_set:
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
    id_usuario_executor: UUID | None = None,
    selected_external_ids: list[str] | None = None,
    simulated_user_id: UUID | None = None,
    simulated_unit_id: UUID | None = None,
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
            id_usuario_executor=id_usuario_executor,
            selected_external_ids=selected_external_ids,
            simulated_user_id=simulated_user_id,
            simulated_unit_id=simulated_unit_id,
        )
        results.append(hist)

    return results


async def preview_endpoint_sync(
    db: Session,
    endpoint_id: UUID,
    simulated_user_id: UUID | None = None,
    simulated_unit_id: UUID | None = None,
    current_user: Usuario | None = None,
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

    # Build De-Para Lookups from regras_de_para or legacy lists
    unit_depara: dict[str, UUID | None] = {}
    user_depara: dict[str, UUID] = {}
    status_map: dict[str, str] = {}

    if mapeamento.regras_de_para:
        for r in mapeamento.regras_de_para:
            if isinstance(r, dict):
                tipo = r.get("tipo")
                for v in (r.get("valores") or []):
                    if isinstance(v, dict):
                        de_val = str(v.get("de", "")).strip()
                        para_val = str(v.get("para", "")).strip()
                        if de_val and para_val:
                            if tipo == "STATUS":
                                status_map[de_val] = para_val
                            elif tipo == "UNIDADE":
                                try:
                                    unit_depara[de_val.upper()] = UUID(para_val)
                                except Exception:
                                    pass
                            elif tipo == "USUARIO":
                                try:
                                    user_depara[de_val.lower()] = UUID(para_val)
                                except Exception:
                                    pass

    if not unit_depara and mapeamento.map_unidades_values:
        for u in mapeamento.map_unidades_values:
            if isinstance(u, dict):
                code = str(u.get("codigo_externo", "")).strip().upper()
                raw_uid = u.get("id_unidade")
                unit_depara[code] = UUID(raw_uid) if raw_uid else None

    if not user_depara and mapeamento.map_usuarios_values:
        for usr in mapeamento.map_usuarios_values:
            if isinstance(usr, dict):
                ident = str(usr.get("identificador_externo", "")).strip().lower()
                raw_usrid = usr.get("id_usuario")
                if raw_usrid:
                    user_depara[ident] = UUID(raw_usrid)

    if not status_map and mapeamento.map_status_values:
        status_map = dict(mapeamento.map_status_values or {})

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
         any(t in (p.valor_template or "") for t in ("{codigo_unidade}", "{sigla_unidade}", "{id_unidade}", "{unit.", "{unidade.")))
        for p in params_objs
    ) or any(t in (endpoint.path or "") for t in ("{codigo_unidade}", "{sigla_unidade}", "{id_unidade}", "{unit.", "{unidade."))

    has_dynamic_user = any(
        (getattr(p, "tipo_origem", None) == ParametroTipoOrigemEnum.DINAMICO_USUARIO or
         any(t in (p.valor_template or "") for t in ("{usuario_", "{id_usuario}", "{user.", "{usuario.")))
        for p in params_objs
    ) or any(t in (endpoint.path or "") for t in ("{usuario_", "{id_usuario}", "{user.", "{usuario."))

    iteration_contexts: list[dict[str, Any]] = []

    if has_dynamic_unit:
        unit_query = db.query(Unidade).filter(
            Unidade.id_organizacao == integracao.id_organizacao,
            Unidade.inativo == False
        )
        if simulated_unit_id:
            unit_query = unit_query.filter(Unidade.id == simulated_unit_id)
        elif endpoint.escopo_unidades == "SELECIONADAS" and endpoint.unidades_selecionadas:
            unit_query = unit_query.filter(Unidade.id.in_(endpoint.unidades_selecionadas))
        
        units = unit_query.all()
        for u in units:
            u_ctx = {
                "id_organizacao": str(integracao.id_organizacao),
                "id_unidade": str(u.id),
                "codigo_unidade": u.sigla or str(u.id),
                "unidade_id": u.sigla or str(u.id),
                "sigla_unidade": u.sigla or u.nome,
                "nome_unidade": u.nome,
            }
            if u.campos_customizados and isinstance(u.campos_customizados, dict):
                for k, v in u.campos_customizados.items():
                    u_ctx[f"unidade_{k}"] = str(v) if v is not None else ""
                    u_ctx[k] = str(v) if v is not None else ""
            iteration_contexts.append(u_ctx)

    elif has_dynamic_user:
        user_rows = db.query(Usuario, UsuarioOrganizacao).join(
            UsuarioOrganizacao, UsuarioOrganizacao.id_usuario == Usuario.id
        ).filter(
            UsuarioOrganizacao.id_organizacao == integracao.id_organizacao,
            UsuarioOrganizacao.inativo == False,
            Usuario.inativo == False
        )
        if simulated_user_id:
            user_rows = user_rows.filter(Usuario.id == simulated_user_id)
        elif endpoint.escopo_usuarios == "USUARIO_LOGADO":
            active_target = current_user.id if current_user else None
            if active_target:
                user_rows = user_rows.filter(Usuario.id == active_target)
        elif endpoint.escopo_usuarios == "SELECIONADOS" and endpoint.usuarios_selecionados:
            user_rows = user_rows.filter(Usuario.id.in_(endpoint.usuarios_selecionados))
        # Se escopo_usuarios == 'TODOS', user_rows itera todos os membros da organização
        
        for u, uo in user_rows.all():
            clean_cpf = u.cpf.replace('.', '').replace('-', '').strip() if u.cpf else ""
            usr_ctx = {
                "id_organizacao": str(integracao.id_organizacao),
                "id_usuario": str(u.id),
                "usuario_cpf": clean_cpf,
                "cpf_usuario": clean_cpf,
                "usuario_email": u.email or "",
                "usuario_login": u.usuario or u.email or "",
                "usuario_nome": u.nome or "",
            }
            if uo.campos_customizados and isinstance(uo.campos_customizados, dict):
                for k, v in uo.campos_customizados.items():
                    usr_ctx[f"usuario_{k}"] = str(v) if v is not None else ""
                    usr_ctx[k] = str(v) if v is not None else ""
            iteration_contexts.append(usr_ctx)

    else:
        iteration_contexts.append({"id_organizacao": str(integracao.id_organizacao)})

    raw_items_with_context: list[Tuple[dict[str, Any], dict[str, Any]]] = []
    total_erros = 0
    warnings: list[str] = []
    motivos_erros: list[SyncPreviewErrorDetail] = []

    for ctx in iteration_contexts:
        status_code, _, payload, _, _, _ = await execute_integrated_request(
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
    preview_items_dict: dict[str, SyncPreviewItem] = {}

    for item, ctx in raw_items_with_context:
        ext_id = None
        if mapeamento.external_id_mode == "COMPOSITE":
            ext_id = build_composite_key(
                item,
                mapeamento.external_id_composite_template or "",
                mapeamento.external_id_composite_paths
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
        dt_atual = parse_date_safe(extract_field_value(item, mapeamento.campo_data_atualizacao)) if getattr(mapeamento, "campo_data_atualizacao", None) else None
        dt_concl = parse_date_safe(extract_field_value(item, mapeamento.campo_data_conclusao)) if getattr(mapeamento, "campo_data_conclusao", None) else None
        raw_status = str(extract_field_value(item, mapeamento.campo_status) or "")
        progresso = parse_percent_safe(extract_field_value(item, mapeamento.campo_progresso))

        ext_link = resolve_item_url_template(mapeamento.campo_link_externo, item)
        projeto = safe_field_str(extract_field_value(item, mapeamento.campo_projeto)) if getattr(mapeamento, "campo_projeto", None) else None
        prioridade = safe_field_str(extract_field_value(item, mapeamento.campo_prioridade)) if getattr(mapeamento, "campo_prioridade", None) else None
        tipo_anotacao = safe_field_str(extract_field_value(item, mapeamento.campo_tipo_anotacao)) if mapeamento.campo_tipo_anotacao else None
        autor = safe_field_str(extract_field_value(item, mapeamento.campo_autor)) if getattr(mapeamento, "campo_autor", None) else None
        codigo = safe_field_str(extract_field_value(item, mapeamento.campo_codigo)) if getattr(mapeamento, "campo_codigo", None) else None
        valor_pretendido = parse_float_safe(extract_field_value(item, mapeamento.campo_valor_pretendido)) if getattr(mapeamento, "campo_valor_pretendido", None) else None
        valor_atual = parse_float_safe(extract_field_value(item, mapeamento.campo_valor_atual)) if getattr(mapeamento, "campo_valor_atual", None) else None

        acao = "CRIAR"
        ja_existe = False
        campos_alterados: list[str] = []
        valores_anteriores: dict[str, Any] = {}

        meta_status: MetaStatusEnum | None = None
        entrega_status: EntregaStatusEnum | None = None

        if endpoint.tipo_integracao.value == "RECEBER_METAS":
            meta_status = map_status_to_meta_enum(raw_status, mapeamento.map_status_values)
            existing = db.query(Meta).filter(
                Meta.id_integracao_config == integracao.id,
                Meta.external_id == ext_id,
                Meta.inativo == False
            ).first()
            if existing:
                ja_existe = True
                if existing.titulo != titulo:
                    campos_alterados.append("titulo")
                    valores_anteriores["titulo"] = existing.titulo
                if existing.status != meta_status:
                    campos_alterados.append("status")
                    valores_anteriores["status"] = existing.status.value if hasattr(existing.status, "value") else str(existing.status)
                if valor_pretendido is not None and float(existing.valor_meta_pretendida or 0) != valor_pretendido:
                    campos_alterados.append("valor_pretendido")
                    valores_anteriores["valor_pretendido"] = float(existing.valor_meta_pretendida or 0)
                if valor_atual is not None and float(existing.valor_meta_atual or 0) != valor_atual:
                    campos_alterados.append("valor_atual")
                    valores_anteriores["valor_atual"] = float(existing.valor_meta_atual or 0)
                if target_unit_id and existing.id_unidade != target_unit_id:
                    campos_alterados.append("unidade")
                    valores_anteriores["unidade"] = existing.unidade.nome if existing.unidade else str(existing.id_unidade)
                if dt_ini and existing.data_inicio != dt_ini:
                    campos_alterados.append("data_inicio")
                    valores_anteriores["data_inicio"] = existing.data_inicio.isoformat() if existing.data_inicio else None
                if dt_fim and existing.data_fim != dt_fim:
                    campos_alterados.append("data_fim")
                    valores_anteriores["data_fim"] = existing.data_fim.isoformat() if existing.data_fim else None
                if codigo and existing.codigo != codigo:
                    campos_alterados.append("codigo")
                    valores_anteriores["codigo"] = existing.codigo

                if len(campos_alterados) > 0:
                    acao = "ATUALIZAR"
                    total_atualizados += 1
                else:
                    acao = "INALTERADO"
                    total_inalterados += 1
            else:
                acao = "CRIAR"
                total_novos += 1
        elif endpoint.tipo_integracao.value == "RECEBER_TAREFAS":
            acao = "VISUALIZAR"
            total_novos += 1
        else:
            entrega_status = map_status_to_entrega_enum(raw_status, mapeamento.map_status_values)
            existing = db.query(Entrega).filter(
                Entrega.id_integracao_config == integracao.id,
                Entrega.external_id == ext_id,
                Entrega.inativo == False
            ).first()
            if existing:
                ja_existe = True
                if existing.titulo != titulo:
                    campos_alterados.append("titulo")
                    valores_anteriores["titulo"] = existing.titulo
                if existing.status != entrega_status:
                    campos_alterados.append("status")
                    valores_anteriores["status"] = existing.status.value if hasattr(existing.status, "value") else str(existing.status)
                if progresso is not None and existing.progresso_percentual != progresso:
                    campos_alterados.append("progresso_percentual")
                    valores_anteriores["progresso_percentual"] = existing.progresso_percentual
                if target_user_id and existing.id_usuario_responsavel != target_user_id:
                    campos_alterados.append("responsavel")
                    valores_anteriores["responsavel"] = existing.usuario_responsavel.nome if existing.usuario_responsavel else str(existing.id_usuario_responsavel)
                if target_unit_id and existing.id_unidade != target_unit_id:
                    campos_alterados.append("unidade")
                    valores_anteriores["unidade"] = existing.unidade.nome if existing.unidade else str(existing.id_unidade)
                if dt_ini and existing.data_inicio != dt_ini:
                    campos_alterados.append("data_inicio")
                    valores_anteriores["data_inicio"] = existing.data_inicio.isoformat() if existing.data_inicio else None
                if dt_fim and existing.data_fim != dt_fim:
                    campos_alterados.append("data_fim")
                    valores_anteriores["data_fim"] = existing.data_fim.isoformat() if existing.data_fim else None
                if codigo and existing.codigo != codigo:
                    campos_alterados.append("codigo")
                    valores_anteriores["codigo"] = existing.codigo

                if len(campos_alterados) > 0:
                    acao = "ATUALIZAR"
                    total_atualizados += 1
                else:
                    acao = "INALTERADO"
                    total_inalterados += 1
            else:
                acao = "CRIAR"
                total_novos += 1

        status_item = raw_status
        if not status_item:
            if endpoint.tipo_integracao.value == "RECEBER_METAS":
                status_item = meta_status.value if meta_status else "NAO_INICIADA"
            elif endpoint.tipo_integracao.value == "RECEBER_TAREFAS":
                status_item = "ABERTA"
            else:
                status_item = entrega_status.value if entrega_status else "NAO_INICIADA"

        if ext_id in preview_items_dict:
            preview_items_dict[ext_id].quantidade_registros += 1
        else:
            preview_items_dict[ext_id] = SyncPreviewItem(
                external_id=ext_id,
                quantidade_registros=1,
                ja_existe=ja_existe,
                campos_alterados=campos_alterados,
                valores_anteriores=valores_anteriores if valores_anteriores else None,
                titulo=titulo,
                tipo_integracao=endpoint.tipo_integracao,
                acao=acao,
                status=status_item,
                data_inicio=dt_ini.isoformat() if dt_ini else None,
                data_fim=dt_fim.isoformat() if dt_fim else None,
                data_criacao=dt_ini.isoformat() if dt_ini else None,
                data_atualizacao=dt_atual.isoformat() if dt_atual else (dt_concl.isoformat() if dt_concl else (dt_fim.isoformat() if dt_fim else None)),
                usuario_responsavel_nome=user_name,
                unidade_nome=unit_name,
                progresso_percentual=progresso,
                link_externo=ext_link,
                projeto=projeto,
                prioridade=prioridade,
                tipo_anotacao=tipo_anotacao,
                autor=autor,
                codigo=codigo,
                valor_pretendido=valor_pretendido,
                valor_atual=valor_atual,
                responsavel_identificador=str(resp_val) if resp_val else None,
                unidade_identificador=str(raw_unit_code) if raw_unit_code else None,
            )

    preview_items = list(preview_items_dict.values())
    preview_items.sort(
        key=lambda item: (item.data_atualizacao or item.data_criacao or item.data_fim or item.data_inicio or ""),
        reverse=True
    )
    preview_items = preview_items[:50]

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
    integracao_id: UUID,
    simulated_user_id: UUID | None = None,
    simulated_unit_id: UUID | None = None,
    current_user: Usuario | None = None,
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
            ep_preview = await preview_endpoint_sync(
                db=db,
                endpoint_id=ep.id,
                simulated_user_id=simulated_user_id,
                simulated_unit_id=simulated_unit_id,
                current_user=current_user,
            )
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

    dedup_all_items: dict[tuple, SyncPreviewItem] = {}
    for it in all_items:
        key = (it.tipo_integracao.value, it.external_id)
        if key in dedup_all_items:
            dedup_all_items[key].quantidade_registros += it.quantidade_registros
        else:
            dedup_all_items[key] = it
    all_items = list(dedup_all_items.values())
    all_items.sort(
        key=lambda item: (item.data_atualizacao or item.data_criacao or item.data_fim or item.data_inicio or ""),
        reverse=True
    )

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


async def fetch_live_user_tasks(
    db: Session,
    id_organizacao: UUID,
    usuario: Usuario,
    id_unidade: UUID | None = None,
    id_endpoint: UUID | None = None,
    funcionalidade: str = "REGISTRO_DIARIO",
    data_referencia: str | None = None,
    parametros_runtime: dict[str, Any] | None = None,
) -> LiveTasksResponse:
    """Fetches on-demand external tasks in real-time for the user in the active organization context."""
    all_raw_endpoints = (
        db.query(IntegracaoEndpoint)
        .join(IntegracaoConfig, IntegracaoConfig.id == IntegracaoEndpoint.id_integracao_config)
        .filter(
            IntegracaoConfig.id_organizacao == id_organizacao,
            IntegracaoConfig.inativo == False,
            IntegracaoConfig.ativo == True,
            IntegracaoEndpoint.tipo_integracao == TipoIntegracaoEnum.RECEBER_TAREFAS,
            IntegracaoEndpoint.inativo == False,
            IntegracaoEndpoint.ativo == True,
        )
        .all()
    )

    # Filter endpoints eligible for requested functionality
    eligible_endpoints = []
    for ep in all_raw_endpoints:
        funcs = ep.funcionalidades_habilitadas or ["GESTAO_INTEGRACOES", "REGISTRO_DIARIO"]
        if funcionalidade in funcs:
            eligible_endpoints.append(ep)

    # Order candidates by nome ASC
    eligible_endpoints.sort(key=lambda ep: (ep.nome or "").lower())

    endpoints_disponiveis = [
        EndpointOpcaoItem(
            id=ep.id,
            nome=ep.nome,
            tipo_integracao=ep.tipo_integracao,
            provedor=ep.integracao_config.provedor.value if ep.integracao_config and ep.integracao_config.provedor else None,
            modo_execucao=ep.modo_execucao,
            ativo_sincronizacao=ep.ativo_sincronizacao,
        )
        for ep in eligible_endpoints
    ]

    if not eligible_endpoints:
        return LiveTasksResponse(
            success=True,
            modo_execucao=ModoExecucaoEnum.AUTOMATICO,
            total_tarefas=0,
            tarefas=[],
            endpoints_consultados=[],
            endpoint_ativo_id=None,
            endpoint_ativo_nome=None,
            endpoints_disponiveis=[],
            erros_ou_avisos=[],
        )

    # If id_endpoint is specified, pick that endpoint; otherwise pick first (ordered ASC)
    target_endpoints = []
    if id_endpoint:
        matched = [ep for ep in eligible_endpoints if str(ep.id) == str(id_endpoint)]
        if matched:
            target_endpoints = matched
        else:
            matched_raw = [ep for ep in all_raw_endpoints if str(ep.id) == str(id_endpoint)]
            target_endpoints = matched_raw if matched_raw else [eligible_endpoints[0]]
    else:
        target_endpoints = [eligible_endpoints[0]]

    active_ep = target_endpoints[0] if target_endpoints else None

    vinculo = db.query(UsuarioOrganizacao).filter(
        UsuarioOrganizacao.id_organizacao == id_organizacao,
        UsuarioOrganizacao.id_usuario == usuario.id,
        UsuarioOrganizacao.inativo == False,
    ).first()

    clean_cpf = usuario.cpf.replace('.', '').replace('-', '').strip() if usuario.cpf else ""
    ref_date_str = str(data_referencia).strip() if data_referencia else now_in_app_timezone().strftime("%Y-%m-%d")

    user_context: dict[str, Any] = {
        "id_organizacao": str(id_organizacao),
        "id_usuario": str(usuario.id),
        "usuario_cpf": clean_cpf,
        "cpf_usuario": clean_cpf,
        "usuario_email": usuario.email or "",
        "usuario_login": usuario.usuario or "",
        "data_referencia": ref_date_str,
        "data_selecionada": ref_date_str,
        "data_diario": ref_date_str,
    }
    if parametros_runtime and isinstance(parametros_runtime, dict):
        for k, v in parametros_runtime.items():
            if v is not None:
                user_context[str(k)] = str(v)

    if vinculo and vinculo.campos_customizados and isinstance(vinculo.campos_customizados, dict):
        for k, v in vinculo.campos_customizados.items():
            user_context[f"usuario_{k}"] = str(v) if v is not None else ""
            user_context[k] = str(v) if v is not None else ""

    if id_unidade:
        unidade = db.query(Unidade).filter(
            Unidade.id == id_unidade,
            Unidade.id_organizacao == id_organizacao,
            Unidade.inativo == False,
        ).first()
        if unidade:
            user_context["id_unidade"] = str(unidade.id)
            user_context["codigo_unidade"] = unidade.sigla or str(unidade.id)
            user_context["unidade_id"] = unidade.sigla or str(unidade.id)
            user_context["sigla_unidade"] = unidade.sigla or unidade.nome
            user_context["nome_unidade"] = unidade.nome
            if unidade.campos_customizados and isinstance(unidade.campos_customizados, dict):
                for k, v in unidade.campos_customizados.items():
                    user_context[f"unidade_{k}"] = str(v) if v is not None else ""
                    user_context[k] = str(v) if v is not None else ""

    all_tasks: list[LiveTaskItem] = []
    endpoints_consultados: list[str] = []
    erros_ou_avisos: list[str] = []
    overall_mode = ModoExecucaoEnum.AUTOMATICO

    for ep in target_endpoints:
        # Verifica se o endpoint está configurado para o escopo do usuário ativo
        if ep.escopo_usuarios == "SELECIONADOS" and ep.usuarios_selecionados:
            user_ids_str = [str(uid) for uid in ep.usuarios_selecionados]
            if str(usuario.id) not in user_ids_str:
                continue

        endpoints_consultados.append(ep.nome)
        if ep.modo_execucao == ModoExecucaoEnum.BOTAO_NA_FUNCIONALIDADE:
            overall_mode = ModoExecucaoEnum.BOTAO_NA_FUNCIONALIDADE

        mapeamento = ep.mapeamento
        if not mapeamento or mapeamento.inativo:
            erros_ou_avisos.append(f"Endpoint '{ep.nome}' não possui mapeamento configurado.")
            continue

        params_objs = []
        if ep.parametros_config:
            for p in ep.parametros_config:
                if isinstance(p, dict):
                    params_objs.append(ParametroConfigSchema(**p))
                elif isinstance(p, ParametroConfigSchema):
                    params_objs.append(p)

        try:
            status_code, _, payload, _, err_msg, _ = await execute_integrated_request(
                url_base=ep.integracao_config.url_base,
                path=ep.path,
                metodo_http=ep.metodo_http,
                tipo_autenticacao=ep.integracao_config.tipo_autenticacao,
                auth_endpoint_path=ep.integracao_config.auth_endpoint_path,
                auth_metodo_http=ep.integracao_config.auth_metodo_http,
                auth_headers=ep.integracao_config.auth_headers,
                auth_payload=ep.integracao_config.auth_payload,
                auth_token_path=ep.integracao_config.auth_token_path,
                auth_static_config=ep.integracao_config.auth_static_config,
                headers_padrao=ep.integracao_config.headers_padrao,
                headers_custom=ep.headers_custom,
                parametros_config=params_objs,
                corpo_requisicao=ep.corpo_requisicao,
                context=user_context,
                timeout=20.0,
            )

            if not (200 <= status_code < 300) or payload is None:
                erros_ou_avisos.append(f"Endpoint '{ep.nome}' retornou status {status_code}: {err_msg or 'Erro na requisição'}")
                continue

            raw_items = extract_items_by_path(payload, mapeamento.items_root_path or "$")
            if not isinstance(raw_items, list):
                raw_items = [raw_items] if isinstance(raw_items, dict) else []

            for idx, raw_item in enumerate(raw_items):
                if not isinstance(raw_item, dict):
                    continue

                if mapeamento.external_id_mode == "COMPOSITE":
                    task_id = build_composite_key(raw_item, mapeamento.external_id_composite_template, mapeamento.external_id_composite_paths)
                else:
                    ext_id_path = mapeamento.campo_codigo or mapeamento.external_id_path or "id"
                    task_id = str(extract_field_value(raw_item, ext_id_path) or f"task-{idx+1}")

                titulo = str(extract_field_value(raw_item, mapeamento.campo_titulo) or f"Tarefa {task_id}")
                descricao = extract_field_value(raw_item, mapeamento.campo_descricao)
                descricao_str = str(descricao) if descricao is not None else None

                raw_status = str(extract_field_value(raw_item, mapeamento.campo_status) or "")
                map_status = dict(mapeamento.map_status_values or {})
                mapped_status = map_status.get(raw_status, raw_status) if raw_status else None

                progresso = parse_percent_safe(extract_field_value(raw_item, mapeamento.campo_progresso))
                dt_ini = parse_date_safe(extract_field_value(raw_item, mapeamento.campo_data_inicio))
                dt_atual = parse_date_safe(extract_field_value(raw_item, mapeamento.campo_data_atualizacao)) if getattr(mapeamento, "campo_data_atualizacao", None) else None

                projeto = safe_field_str(extract_field_value(raw_item, mapeamento.campo_projeto)) if getattr(mapeamento, "campo_projeto", None) else None
                prioridade = safe_field_str(extract_field_value(raw_item, mapeamento.campo_prioridade)) if getattr(mapeamento, "campo_prioridade", None) else None
                autor = safe_field_str(extract_field_value(raw_item, mapeamento.campo_autor)) if getattr(mapeamento, "campo_autor", None) else None
                tracker = safe_field_str(extract_field_value(raw_item, mapeamento.campo_tipo_anotacao)) if mapeamento.campo_tipo_anotacao else None
                responsavel = safe_field_str(extract_field_value(raw_item, mapeamento.campo_responsavel)) if mapeamento.campo_responsavel else None

                # Build external ticket URL
                url_externa = None
                if getattr(mapeamento, "campo_link_externo", None):
                    url_externa = resolve_item_url_template(mapeamento.campo_link_externo, raw_item)

                if not url_externa:
                    base_url = ep.integracao_config.url_base.rstrip('/') if ep.integracao_config.url_base else None
                    if base_url and task_id and not str(task_id).startswith("task-"):
                        if ep.integracao_config.provedor.value == "REDMINE":
                            url_externa = f"{base_url}/issues/{task_id}"
                        elif ep.integracao_config.provedor.value == "JIRA":
                            url_externa = f"{base_url}/browse/{task_id}"

                extras_dict = {}
                campos_extras = getattr(mapeamento, "campos_extras", None) or mapeamento.campos_extras
                if campos_extras:
                    for extra_item in (campos_extras or []):
                        if isinstance(extra_item, dict) and "chave" in extra_item and "caminho" in extra_item:
                            val = extract_field_value(raw_item, extra_item["caminho"])
                            if val is not None:
                                extras_dict[extra_item["chave"]] = val

                all_tasks.append(LiveTaskItem(
                    id=task_id,
                    titulo=titulo,
                    descricao=descricao_str,
                    status=mapped_status,
                    projeto=projeto,
                    tracker=tracker,
                    prioridade=prioridade,
                    autor=autor,
                    responsavel=responsavel,
                    data_criacao=str(dt_ini) if dt_ini else None,
                    data_atualizacao=str(dt_atual) if dt_atual else None,
                    percentual_feito=progresso,
                    url_externa=url_externa,
                    origem_provedor=ep.integracao_config.provedor.value if ep.integracao_config.provedor else "CUSTOM_REST",
                    detalhes_extras=extras_dict if extras_dict else None,
                ))
        except Exception as ex:
            erros_ou_avisos.append(f"Erro ao processar endpoint '{ep.nome}': {str(ex)}")

    all_tasks.sort(
        key=lambda t: (t.data_atualizacao or t.data_criacao or ""),
        reverse=True
    )

    return LiveTasksResponse(
        success=True,
        modo_execucao=overall_mode,
        total_tarefas=len(all_tasks),
        tarefas=all_tasks,
        endpoints_consultados=endpoints_consultados,
        endpoint_ativo_id=active_ep.id if active_ep else None,
        endpoint_ativo_nome=active_ep.nome if active_ep else None,
        endpoints_disponiveis=endpoints_disponiveis,
        erros_ou_avisos=erros_ou_avisos,
    )


