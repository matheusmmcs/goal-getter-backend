import time
import re
import json
import base64
import urllib.parse
from datetime import datetime, date
from typing import Any, Tuple
import httpx

from app.models.enums import (
    MetodoHttpEnum,
    TipoAutenticacaoEnum,
    TipoIntegracaoEnum,
    ParametroLocalizacaoEnum,
    ParametroTipoOrigemEnum,
    EntregaStatusEnum,
    MetaStatusEnum,
)
from app.schemas.integracao import (
    TestConnectionRequest,
    TestConnectionResponse,
    InspectSchemaRequest,
    InspectSchemaResponse,
    JsonTreeNode,
    PreviewMappingRequest,
    PreviewMappingResponse,
    TransformedItemPreview,
    IntegracaoMapeamentoBase,
    ParametroConfigSchema,
)


def is_safe_url(url_str: str) -> bool:
    """Validates URL to ensure valid protocol and prevent SSRF attacks."""
    try:
        parsed = urllib.parse.urlparse(url_str)
        if parsed.scheme not in ('http', 'https'):
            return False
        if not parsed.hostname:
            return False
        return True
    except Exception:
        return False


def join_url(url_base: str, path: str | None) -> str:
    """Joins URL_INTEGRACAO base with relative path cleanly."""
    base = url_base.strip()
    if not path or not path.strip():
        return base
    p = path.strip()
    if p.startswith('http://') or p.startswith('https://'):
        return p
    return f"{base.rstrip('/')}/{p.lstrip('/')}"


def resolve_template_string(template_str: str, context: dict[str, Any]) -> str:
    """Substitutes template tags like {ano_atual}, {data_hoje}, {codigo_unidade} from context."""
    if not template_str:
        return ""
    now = datetime.now()
    default_context = {
        "ano_atual": str(now.year),
        "mes_atual": f"{now.month:02d}",
        "data_hoje": now.strftime("%Y-%m-%d"),
        "data_ontem": date.fromordinal(now.toordinal() - 1).strftime("%Y-%m-%d"),
        "ano": str(now.year),
        "mes": f"{now.month:02d}",
    }
    merged = {**default_context, **context}
    
    # Expande automaticamente apelidos para tags de campos customizados (ex: usuario_xpto <-> xpto)
    extra_aliases = {}
    for k, v in merged.items():
        if v is not None:
            if k.startswith("usuario_"):
                short_k = k[len("usuario_"):]
                if short_k not in merged:
                    extra_aliases[short_k] = v
            elif k.startswith("unidade_"):
                short_k = k[len("unidade_"):]
                if short_k not in merged:
                    extra_aliases[short_k] = v
            else:
                usr_k = f"usuario_{k}"
                if usr_k not in merged:
                    extra_aliases[usr_k] = v
                und_k = f"unidade_{k}"
                if und_k not in merged:
                    extra_aliases[und_k] = v
    merged.update(extra_aliases)

    result = template_str
    for k, v in merged.items():
        if v is not None:
            result = result.replace(f"{{{k}}}", str(v))
    return result


def extract_value_by_dot_path(obj: Any, dot_path: str | None) -> Any:
    """Navigates through dot notation to extract a nested value from dict/list."""
    if not dot_path or obj is None:
        return None
    clean_path = dot_path.lstrip('$.').strip()
    if not clean_path:
        return obj
    segments = clean_path.split('.')
    current = obj
    for seg in segments:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(seg)
        elif isinstance(current, list):
            if seg.isdigit():
                idx = int(seg)
                current = current[idx] if idx < len(current) else None
            else:
                collected = []
                for item in current:
                    if isinstance(item, dict) and seg in item:
                        collected.append(item[seg])
                current = collected if collected else None
        else:
            return None
    return current


async def obtain_dynamic_auth_token(
    url_base: str,
    auth_endpoint_path: str | None,
    auth_metodo_http: MetodoHttpEnum | None,
    auth_headers: dict[str, str] | None,
    auth_payload: dict[str, Any] | None,
    auth_token_path: str | None,
    timeout: float = 12.0,
) -> Tuple[str | None, str | None]:
    """Performs dynamic login request to {URL_INTEGRACAO}/{auth_endpoint_path} and extracts token."""
    login_url = join_url(url_base, auth_endpoint_path or "/auth/login")
    if not is_safe_url(login_url):
        return None, "URL de login dinâmica inválida."

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "GoalGetter-DynamicAuth/1.0",
    }
    if auth_headers:
        headers.update(auth_headers)

    method = (auth_metodo_http or MetodoHttpEnum.POST).value.upper()

    try:
        async with httpx.AsyncClient(timeout=timeout, verify=True, follow_redirects=True) as client:
            if method == "POST":
                resp = await client.post(login_url, json=auth_payload or {}, headers=headers)
            else:
                resp = await client.get(login_url, params=auth_payload or {}, headers=headers)

            if not (200 <= resp.status_code < 300):
                return None, f"Falha na autenticação dinâmica. Status {resp.status_code}: {resp.text[:300]}"

            try:
                data = resp.json()
            except Exception:
                return None, f"Resposta de autenticação não é um JSON válido: {resp.text[:200]}"

            token_path = auth_token_path or "access_token"
            token_val = extract_value_by_dot_path(data, token_path)

            if not token_val and token_path == "access_token":
                token_val = extract_value_by_dot_path(data, "token") or extract_value_by_dot_path(data, "data.token") or extract_value_by_dot_path(data, "data.access_token")

            if not token_val:
                return None, f"Token não encontrado no caminho '{token_path}' da resposta de autenticação."

            return str(token_val), None
    except Exception as e:
        return None, f"Erro de conexão na autenticação dinâmica: {str(e)}"


async def prepare_request_headers_and_auth(
    url_base: str,
    tipo_autenticacao: TipoAutenticacaoEnum,
    auth_endpoint_path: str | None = None,
    auth_metodo_http: MetodoHttpEnum | None = None,
    auth_headers: dict[str, str] | None = None,
    auth_payload: dict[str, Any] | None = None,
    auth_token_path: str | None = None,
    auth_static_config: dict[str, Any] | None = None,
    headers_padrao: dict[str, str] | None = None,
    headers_custom: dict[str, str] | None = None,
) -> Tuple[dict[str, str], Any, str | None]:
    """Prepares HTTP headers, basic auth tuple, and dynamic token if applicable."""
    headers: dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": "GoalGetter-LegoIntegration/2.0",
    }
    if headers_padrao:
        headers.update(headers_padrao)
    if headers_custom:
        headers.update(headers_custom)

    auth_tuple: Any = None
    extracted_token: str | None = None

    if tipo_autenticacao == TipoAutenticacaoEnum.DYNAMIC_LOGIN:
        token, err = await obtain_dynamic_auth_token(
            url_base=url_base,
            auth_endpoint_path=auth_endpoint_path,
            auth_metodo_http=auth_metodo_http,
            auth_headers=auth_headers,
            auth_payload=auth_payload,
            auth_token_path=auth_token_path,
        )
        if err:
            raise ValueError(err)
        if token:
            extracted_token = token
            headers["Authorization"] = f"Bearer {token}"

    elif tipo_autenticacao == TipoAutenticacaoEnum.BEARER_TOKEN and auth_static_config:
        token = auth_static_config.get("token") or auth_static_config.get("bearer_token")
        if token:
            extracted_token = token
            headers["Authorization"] = f"Bearer {token}"

    elif tipo_autenticacao == TipoAutenticacaoEnum.API_KEY_HEADER and auth_static_config:
        header_name = auth_static_config.get("header_name", "X-API-KEY")
        header_value = auth_static_config.get("header_value", "")
        if header_name and header_value:
            headers[header_name] = header_value

    elif tipo_autenticacao == TipoAutenticacaoEnum.API_KEY_QUERY and auth_static_config:
        token = (
            auth_static_config.get("api_key")
            or auth_static_config.get("param_value")
            or auth_static_config.get("key")
            or auth_static_config.get("token")
        )
        if token:
            extracted_token = str(token)

    elif tipo_autenticacao == TipoAutenticacaoEnum.BASIC_AUTH and auth_static_config:
        username = auth_static_config.get("username", "")
        password = auth_static_config.get("password", "")
        auth_tuple = (username, password)

    elif tipo_autenticacao == TipoAutenticacaoEnum.CUSTOM_HEADER and auth_static_config:
        for k, v in auth_static_config.items():
            if isinstance(v, str):
                headers[k] = v

    return headers, auth_tuple, extracted_token


async def execute_integrated_request(
    url_base: str,
    path: str = "",
    metodo_http: MetodoHttpEnum = MetodoHttpEnum.GET,
    tipo_autenticacao: TipoAutenticacaoEnum = TipoAutenticacaoEnum.NONE,
    auth_endpoint_path: str | None = None,
    auth_metodo_http: MetodoHttpEnum | None = None,
    auth_headers: dict[str, str] | None = None,
    auth_payload: dict[str, Any] | None = None,
    auth_token_path: str | None = None,
    auth_static_config: dict[str, Any] | None = None,
    headers_padrao: dict[str, str] | None = None,
    headers_custom: dict[str, str] | None = None,
    parametros_config: list[ParametroConfigSchema] | None = None,
    corpo_requisicao: str | None = None,
    context: dict[str, Any] | None = None,
    timeout: float = 15.0,
) -> Tuple[int, float, Any, dict[str, str], str | None]:
    """Executes full integrated HTTP request resolving parameters, path tags, headers, and dynamic auth."""
    ctx = context or {}
    
    # 1. Resolve path template
    resolved_path = resolve_template_string(path, ctx)
    full_url = join_url(url_base, resolved_path)

    if not is_safe_url(full_url):
        raise ValueError(f"URL de destino inválida: {full_url}")

    # 2. Build auth & headers
    headers, auth_tuple, dynamic_token = await prepare_request_headers_and_auth(
        url_base=url_base,
        tipo_autenticacao=tipo_autenticacao,
        auth_endpoint_path=auth_endpoint_path,
        auth_metodo_http=auth_metodo_http,
        auth_headers=auth_headers,
        auth_payload=auth_payload,
        auth_token_path=auth_token_path,
        auth_static_config=auth_static_config,
        headers_padrao=headers_padrao,
        headers_custom=headers_custom,
    )

    # 3. Process parameters
    query_params: dict[str, Any] = {}
    body_data = None

    if tipo_autenticacao == TipoAutenticacaoEnum.API_KEY_QUERY and auth_static_config:
        param_name = (
            auth_static_config.get("param_name")
            or auth_static_config.get("query_param_name")
            or auth_static_config.get("header_name")
            or "key"
        )
        param_value = (
            auth_static_config.get("api_key")
            or auth_static_config.get("param_value")
            or auth_static_config.get("key")
            or auth_static_config.get("token")
            or ""
        )
        if param_name and param_value:
            query_params[param_name] = param_value

    if parametros_config:
        for p in parametros_config:
            val = resolve_template_string(p.valor_template, ctx)
            if p.obrigatorio and (val is None or val == ""):
                raise ValueError(f"Parâmetro obrigatório '{p.nome}' não pôde ser resolvido com o contexto fornecido.")
            
            loc = p.localizacao
            if loc == ParametroLocalizacaoEnum.QUERY:
                query_params[p.nome] = val
            elif loc == ParametroLocalizacaoEnum.HEADER:
                headers[p.nome] = val
            elif loc == ParametroLocalizacaoEnum.PATH:
                full_url = full_url.replace(f"{{{p.nome}}}", urllib.parse.quote(str(val)))

    if corpo_requisicao and metodo_http == MetodoHttpEnum.POST:
        resolved_body = resolve_template_string(corpo_requisicao, ctx)
        try:
            body_data = json.loads(resolved_body)
            headers["Content-Type"] = "application/json"
        except Exception:
            body_data = resolved_body

    # 4. Perform HTTP call
    start_time = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout, verify=True, follow_redirects=True) as client:
        method = metodo_http.value.upper()
        if method == "POST":
            if isinstance(body_data, (dict, list)):
                resp = await client.post(full_url, json=body_data, params=query_params, headers=headers, auth=auth_tuple)
            else:
                resp = await client.post(full_url, content=body_data, params=query_params, headers=headers, auth=auth_tuple)
        else:
            resp = await client.get(full_url, params=query_params, headers=headers, auth=auth_tuple)

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    resp_headers = {k: v for k, v in resp.headers.items()}

    try:
        parsed_data = resp.json()
    except Exception:
        parsed_data = {"raw_text": resp.text[:2000]}

    return resp.status_code, latency_ms, parsed_data, resp_headers, dynamic_token


async def test_connection(req: TestConnectionRequest) -> TestConnectionResponse:
    """Tests connection to URL_INTEGRACAO base and verifies authentication."""
    try:
        status_code, latency_ms, data, headers_ret, token = await execute_integrated_request(
            url_base=req.url_base,
            path="",
            metodo_http=MetodoHttpEnum.GET,
            tipo_autenticacao=req.tipo_autenticacao,
            auth_endpoint_path=req.auth_endpoint_path,
            auth_metodo_http=req.auth_metodo_http,
            auth_headers=req.auth_headers,
            auth_payload=req.auth_payload,
            auth_token_path=req.auth_token_path,
            auth_static_config=req.auth_static_config,
            headers_padrao=req.headers_padrao,
        )
        is_success = 200 <= status_code < 400
        msg = f"Conexão bem-sucedida (HTTP {status_code}) em {latency_ms}ms" if is_success else f"Servidor respondeu com status {status_code}"
        return TestConnectionResponse(
            success=is_success,
            status_code=status_code,
            latency_ms=latency_ms,
            message=msg,
            headers_returned=headers_ret,
            auth_token_preview=token[:20] + "..." if token else None,
            sample_preview=data if isinstance(data, (dict, list)) else {"preview": str(data)[:200]},
        )
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            status_code=0,
            latency_ms=0.0,
            message=f"Falha ao conectar: {str(e)}",
            headers_returned=None,
            auth_token_preview=None,
            sample_preview=None,
        )


def get_value_type(val: Any) -> str:
    """Returns canonical JSON type string."""
    if val is None:
        return "null"
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, (int, float)):
        return "number"
    if isinstance(val, str):
        return "string"
    if isinstance(val, list):
        return "array"
    if isinstance(val, dict):
        return "object"
    return "unknown"


def build_schema_tree(payload: Any, current_key: str = "root", current_path: str = "$", depth: int = 0) -> list[JsonTreeNode]:
    """Constructs a tree node representation of JSON for the Lego visual mapping tool."""
    if depth > 6 or payload is None:
        return []

    nodes: list[JsonTreeNode] = []

    if isinstance(payload, dict):
        for k, v in payload.items():
            child_path = k if current_path == "$" else f"{current_path}.{k}"
            val_type = get_value_type(v)
            is_arr = isinstance(v, list)

            children = None
            sample_val = v
            if is_arr:
                if len(v) > 0 and isinstance(v[0], dict):
                    children = build_schema_tree(v[0], k, child_path, depth + 1)
                    sample_val = f"[{len(v)} itens]"
                else:
                    sample_val = v[:3] if len(v) > 0 else []
            elif isinstance(v, dict):
                children = build_schema_tree(v, k, child_path, depth + 1)
                sample_val = "{...}"

            nodes.append(JsonTreeNode(
                key=k,
                path=child_path,
                type=val_type,
                sample_value=sample_val if not isinstance(sample_val, (dict, list)) else str(sample_val),
                is_array=is_arr,
                children=children
            ))

    elif isinstance(payload, list):
        if len(payload) > 0:
            first_item = payload[0]
            if isinstance(first_item, dict):
                return build_schema_tree(first_item, current_key, current_path, depth)
            else:
                nodes.append(JsonTreeNode(
                    key="[item]",
                    path=current_path,
                    type=get_value_type(first_item),
                    sample_value=str(first_item),
                    is_array=False,
                    children=None
                ))

    return nodes


def extract_flat_paths(payload: Any, current_path: str = "", depth: int = 0) -> list[str]:
    """Extracts a flat list of dot-separated paths for autocomplete in Lego mapper, traversing objects and arrays."""
    if depth > 6 or payload is None:
        return []

    paths = []
    if isinstance(payload, dict):
        for k, v in payload.items():
            p = f"{current_path}.{k}" if current_path else k
            paths.append(p)
            if isinstance(v, dict):
                paths.extend(extract_flat_paths(v, p, depth + 1))
            elif isinstance(v, list) and len(v) > 0:
                for elem in v[:5]:
                    if isinstance(elem, dict):
                        paths.extend(extract_flat_paths(elem, p, depth + 1))
                    elif isinstance(elem, list):
                        paths.extend(extract_flat_paths(elem, p, depth + 1))
    elif isinstance(payload, list) and len(payload) > 0:
        for elem in payload[:5]:
            if isinstance(elem, dict):
                paths.extend(extract_flat_paths(elem, current_path, depth + 1))
            elif isinstance(elem, list):
                paths.extend(extract_flat_paths(elem, current_path, depth + 1))

    return list(dict.fromkeys(paths))


def detect_candidate_arrays(payload: Any, current_path: str = "$", depth: int = 0) -> list[str]:
    """Finds all array paths that contain objects suitable for items_root_path."""
    if depth > 5 or payload is None:
        return []

    results = []
    if isinstance(payload, list):
        if len(payload) > 0 and isinstance(payload[0], dict):
            results.append(current_path)
    elif isinstance(payload, dict):
        for k, v in payload.items():
            child_path = k if current_path == "$" else f"{current_path}.{k}"
            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                results.append(child_path)
            elif isinstance(v, dict):
                results.extend(detect_candidate_arrays(v, child_path, depth + 1))

    return results


def extract_items_by_path(payload: Any, root_path: str) -> list[Any]:
    """Navigates through dot notation or '$' to extract the items array."""
    if not root_path or root_path.strip() in ('$', '', '.'):
        if isinstance(payload, list):
            return payload
        elif isinstance(payload, dict):
            for v in payload.values():
                if isinstance(v, list):
                    return v
            return [payload]
        return []

    clean_path = root_path.lstrip('$.').strip()
    segments = clean_path.split('.')
    current = payload

    for seg in segments:
        if current is None:
            return []
        if isinstance(current, dict):
            current = current.get(seg)
        elif isinstance(current, list):
            if seg.isdigit():
                idx = int(seg)
                current = current[idx] if idx < len(current) else None
            else:
                collected = []
                for item in current:
                    if isinstance(item, dict) and seg in item:
                        val = item[seg]
                        if isinstance(val, list):
                            collected.extend(val)
                        else:
                            collected.append(val)
                current = collected
        else:
            return []

    if isinstance(current, list):
        return current
    elif isinstance(current, dict):
        return [current]
    return []


def merge_sample_items(items: list[Any]) -> dict[str, Any]:
    """Merges keys and structures from up to 10 sample items to provide a comprehensive schema."""
    merged: dict[str, Any] = {}
    for item in items[:10]:
        if isinstance(item, dict):
            for k, v in item.items():
                if k not in merged or merged[k] is None:
                    merged[k] = v
                elif isinstance(merged[k], dict) and isinstance(v, dict):
                    merged[k] = {**merged[k], **v}
                elif isinstance(merged[k], list) and isinstance(v, list):
                    if len(merged[k]) == 0 and len(v) > 0:
                        merged[k] = v
                    elif len(merged[k]) > 0 and len(v) > 0 and isinstance(merged[k][0], dict) and isinstance(v[0], dict):
                        merged[k][0] = {**merged[k][0], **v[0]}
    return merged


async def inspect_schema(req: InspectSchemaRequest) -> InspectSchemaResponse:
    """Inspects external endpoint or raw payload and returns tree and detected arrays."""
    latency_ms = 0.0
    payload = req.raw_sample

    if payload is None:
        contexts_to_run = req.iteration_contexts if req.iteration_contexts and len(req.iteration_contexts) > 0 else [req.context]
        all_payloads = []
        errors = []
        latencies = []

        for c_idx, ctx in enumerate(contexts_to_run):
            try:
                status_code, lat, data, _, _ = await execute_integrated_request(
                    url_base=req.url_base,
                    path=req.path,
                    metodo_http=req.metodo_http,
                    tipo_autenticacao=req.tipo_autenticacao,
                    auth_endpoint_path=req.auth_endpoint_path,
                    auth_metodo_http=req.auth_metodo_http,
                    auth_headers=req.auth_headers,
                    auth_payload=req.auth_payload,
                    auth_token_path=req.auth_token_path,
                    auth_static_config=req.auth_static_config,
                    headers_padrao=req.headers_padrao,
                    headers_custom=req.headers_custom,
                    parametros_config=req.parametros_config,
                    corpo_requisicao=req.corpo_requisicao,
                    context=ctx,
                )
                latencies.append(lat)
                if 200 <= status_code < 300:
                    if data is not None:
                        all_payloads.append(data)
                else:
                    errors.append(f"Contexto #{c_idx+1} retornou status {status_code}: {str(data)[:150]}")
            except Exception as e:
                errors.append(f"Contexto #{c_idx+1} falhou: {str(e)}")

        if latencies:
            latency_ms = sum(latencies) / len(latencies)

        if not all_payloads:
            error_detail = "; ".join(errors) if errors else "Nenhum dado retornado pelas requisições."
            return InspectSchemaResponse(
                success=False,
                latency_ms=latency_ms,
                detected_arrays=[],
                schema_tree=[],
                discovered_fields=[],
                sample_payload={"error": error_detail}
            )

        if len(all_payloads) == 1:
            payload = all_payloads[0]
        else:
            if all(isinstance(p, list) for p in all_payloads):
                combined = []
                for p in all_payloads:
                    combined.extend(p)
                payload = combined
            elif all(isinstance(p, dict) for p in all_payloads):
                merged_dict: dict[str, Any] = {}
                for p in all_payloads:
                    for k, v in p.items():
                        if k not in merged_dict:
                            merged_dict[k] = v
                        elif isinstance(merged_dict[k], list) and isinstance(v, list):
                            merged_dict[k] = merged_dict[k] + v
                        elif isinstance(merged_dict[k], dict) and isinstance(v, dict):
                            merged_dict[k] = {**merged_dict[k], **v}
                payload = merged_dict
            else:
                payload = all_payloads[0]

    detected_arrays = detect_candidate_arrays(payload)
    if not detected_arrays and isinstance(payload, list):
        detected_arrays = ["$"]

    sample_target = payload
    if detected_arrays:
        first_array_path = detected_arrays[0]
        extracted = extract_items_by_path(payload, first_array_path)
        if extracted and len(extracted) > 0:
            sample_target = merge_sample_items(extracted) if any(isinstance(x, dict) for x in extracted) else extracted[0]

    schema_tree = build_schema_tree(sample_target)
    discovered_fields = extract_flat_paths(sample_target)

    return InspectSchemaResponse(
        success=True,
        latency_ms=latency_ms,
        detected_arrays=detected_arrays,
        schema_tree=schema_tree,
        discovered_fields=discovered_fields,
        sample_payload=payload if isinstance(payload, dict) else (payload[:3] if isinstance(payload, list) else payload)
    )


def extract_field_value(item: dict[str, Any], path: str | None) -> Any:
    """Extracts value using dot notation from a single item."""
    if not path or not isinstance(item, dict):
        return None
    return extract_value_by_dot_path(item, path)


def parse_date_safe(val: Any) -> date | None:
    """Parses various date/datetime representations into date object."""
    if not val:
        return None
    if isinstance(val, (date, datetime)):
        return val if isinstance(val, date) else val.date()
    s = str(val).strip()
    # Format: YYYY-MM-DD
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass
    # Format: DD/MM/YYYY
    match_br = re.match(r"^(\d{2})/(\d{2})/(\d{4})", s)
    if match_br:
        try:
            return date(int(match_br.group(3)), int(match_br.group(2)), int(match_br.group(1)))
        except ValueError:
            pass
    return None


def parse_float_safe(val: Any, default: float = 0.0) -> float:
    """Safely converts numeric or string to float."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    try:
        clean = str(val).replace(',', '.').strip()
        return float(clean)
    except Exception:
        return default


def parse_percent_safe(val: Any, default: int = 0) -> int:
    """Safely converts progress to integer percentage 0-100."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        f = float(val)
        if 0.0 <= f <= 1.0 and f > 0:
            return int(f * 100)
        return max(0, min(100, int(f)))
    try:
        s = str(val).replace('%', '').strip()
        f = float(s)
        if 0.0 <= f <= 1.0 and f > 0:
            return int(f * 100)
        return max(0, min(100, int(f)))
    except Exception:
        return default


def build_composite_key(item: dict[str, Any], template: str | None, paths: list[str] | None) -> str:
    """Builds composite external_id from multiple paths and template."""
    if not paths:
        return str(item.get("id", ""))
    extracted_values = [str(extract_field_value(item, p) or "") for p in paths]
    if template:
        res = template
        for i, val in enumerate(extracted_values):
            res = res.replace(f"{{{i}}}", val)
        for p, val in zip(paths, extracted_values):
            clean_p = p.replace('.', '_')
            res = res.replace(f"{{{clean_p}}}", val)
            res = res.replace(f"{{{p}}}", val)
        return res
def resolve_item_url_template(template_or_field: str | None, item: dict[str, Any]) -> str | None:
    """
    Resolves external link either from a single field path (e.g. 'html_url', 'url')
    or by interpolating a parameterized template string with item fields
    (e.g. 'https://redminedes.ufpi.br/{project.id}/{id}/view').
    """
    if not template_or_field or not isinstance(item, dict):
        return None
    cleaned = str(template_or_field).strip()
    if not cleaned:
        return None

    if "{" in cleaned and "}" in cleaned:
        tokens = re.findall(r"\{([^}]+)\}", cleaned)
        res = cleaned
        for token in tokens:
            val = extract_field_value(item, token.strip())
            val_str = str(val) if val is not None else ""
            res = res.replace(f"{{{token}}}", val_str)
        return res
    else:
        val = extract_field_value(item, cleaned)
        return str(val).strip() if val is not None else None


async def preview_mapping(req: PreviewMappingRequest) -> PreviewMappingResponse:
    """Executes live simulation of Lego mapping transformation for RECEBER_METAS, RECEBER_ENTREGAS or RECEBER_TAREFAS."""
    map_cfg = req.mapeamento
    # Build De-Para lookups from unified regras_de_para or legacy lists
    status_map_dict: dict[str, str] = {}
    unit_map_dict: dict[str, str] = {}
    user_map_dict: dict[str, str] = {}

    if map_cfg.regras_de_para:
        for regra in map_cfg.regras_de_para:
            regra_tipo = regra.tipo.value if hasattr(regra.tipo, "value") else str(regra.tipo)
            if regra_tipo == "STATUS":
                for v in (regra.valores or []):
                    status_map_dict[str(v.de).strip()] = v.para
            elif regra_tipo == "UNIDADE":
                for v in (regra.valores or []):
                    unit_map_dict[str(v.de).strip().upper()] = v.rotulo_externo or v.para
            elif regra_tipo == "USUARIO":
                for v in (regra.valores or []):
                    user_map_dict[str(v.de).strip().lower()] = v.rotulo_externo or v.para

    # Fallback to legacy fields
    if not status_map_dict and map_cfg.map_status_values:
        status_map_dict = map_cfg.map_status_values
    if not unit_map_dict and map_cfg.map_unidades_values:
        for u in map_cfg.map_unidades_values:
            unit_map_dict[str(u.codigo_externo).strip().upper()] = u.nome_externo or str(u.id_unidade)
    if not user_map_dict and map_cfg.map_usuarios_values:
        for usr in map_cfg.map_usuarios_values:
            user_map_dict[str(usr.identificador_externo).strip().lower()] = usr.nome_externo or str(usr.id_usuario)

    transformed: list[TransformedItemPreview] = []
    transformed_dict: dict[str, TransformedItemPreview] = {}
    warnings: list[str] = []

    def transform_single_item(item: dict[str, Any], idx: int, ctx_info: dict[str, Any] | None = None) -> TransformedItemPreview | None:
        if not isinstance(item, dict):
            warnings.append(f"Item #{idx} não é um objeto JSON válido (ignorado).")
            return None

        # External ID
        if map_cfg.external_id_mode == "COMPOSITE":
            ext_id = build_composite_key(item, map_cfg.external_id_composite_template, map_cfg.external_id_composite_paths)
        else:
            ext_id_path = map_cfg.external_id_path or "id"
            ext_id = str(extract_field_value(item, ext_id_path) or f"auto-{idx}")

        # Canonical Title
        titulo = str(extract_field_value(item, map_cfg.campo_titulo) or f"Item {idx + 1}")
        descricao = extract_field_value(item, map_cfg.campo_descricao)
        descricao = str(descricao) if descricao is not None else None
        codigo = str(extract_field_value(item, map_cfg.campo_codigo)) if map_cfg.campo_codigo else None

        # Dates
        dt_ini = parse_date_safe(extract_field_value(item, map_cfg.campo_data_inicio))
        dt_fim = parse_date_safe(extract_field_value(item, map_cfg.campo_data_fim))
        dt_conc = parse_date_safe(extract_field_value(item, map_cfg.campo_data_conclusao))

        # Status & De-Para
        raw_status = str(extract_field_value(item, map_cfg.campo_status) or "").strip()
        default_status = "PLANEJADA" if req.tipo_integracao == TipoIntegracaoEnum.RECEBER_METAS else "NAO_INICIADA"
        mapped_status = status_map_dict.get(raw_status, raw_status) if raw_status else default_status

        # Values & Progress
        progresso = parse_percent_safe(extract_field_value(item, map_cfg.campo_progresso))
        val_ini = parse_float_safe(extract_field_value(item, map_cfg.campo_valor_inicial))
        val_pret = parse_float_safe(extract_field_value(item, map_cfg.campo_valor_pretendido))
        val_atual = parse_float_safe(extract_field_value(item, map_cfg.campo_valor_atual))

        # Responsible & Units
        responsavel = extract_field_value(item, map_cfg.campo_responsavel)
        responsavel_id = str(responsavel).strip() if responsavel is not None else None
        if responsavel_id and responsavel_id.lower() in user_map_dict:
            responsavel_id = user_map_dict[responsavel_id.lower()]
        elif responsavel_id is None and ctx_info and (ctx_info.get("usuario_nome") or ctx_info.get("usuario_login")):
            responsavel_id = ctx_info.get("usuario_nome") or ctx_info.get("usuario_login")

        unidade_ext = extract_field_value(item, map_cfg.campo_unidade_origem)
        unidade_id_str = str(unidade_ext).strip() if unidade_ext is not None else None
        unidade_mapeada = unit_map_dict.get(unidade_id_str.upper()) if unidade_id_str else None

        meta_id = extract_field_value(item, map_cfg.campo_meta_id)
        meta_id_str = str(meta_id) if meta_id is not None else None
        tipo_anotacao = str(extract_field_value(item, map_cfg.campo_tipo_anotacao) or "TODAY") if map_cfg.campo_tipo_anotacao else None

        # Task specific canonical fields
        dt_atualizacao = parse_date_safe(extract_field_value(item, map_cfg.campo_data_atualizacao)) if getattr(map_cfg, "campo_data_atualizacao", None) else None
        projeto = str(extract_field_value(item, map_cfg.campo_projeto)) if getattr(map_cfg, "campo_projeto", None) and extract_field_value(item, map_cfg.campo_projeto) is not None else None
        prioridade = str(extract_field_value(item, map_cfg.campo_prioridade)) if getattr(map_cfg, "campo_prioridade", None) and extract_field_value(item, map_cfg.campo_prioridade) is not None else None
        autor = str(extract_field_value(item, map_cfg.campo_autor)) if getattr(map_cfg, "campo_autor", None) and extract_field_value(item, map_cfg.campo_autor) is not None else None
        link_externo = resolve_item_url_template(getattr(map_cfg, "campo_link_externo", None), item)

        extras_dict: dict[str, Any] = {}
        if getattr(map_cfg, "campos_extras", None):
            for extra_item in map_cfg.campos_extras:
                if isinstance(extra_item, dict) and "chave" in extra_item and "caminho" in extra_item:
                    val = extract_field_value(item, extra_item["caminho"])
                    if val is not None:
                        extras_dict[extra_item["chave"]] = val

        return TransformedItemPreview(
            tipo_integracao=req.tipo_integracao,
            external_id=ext_id,
            titulo=titulo,
            descricao=descricao,
            codigo=codigo,
            data_inicio=dt_ini,
            data_fim=dt_fim,
            data_conclusao=dt_conc,
            data_atualizacao=dt_atualizacao,
            status=mapped_status,
            progresso_percentual=progresso,
            valor_inicial=val_ini,
            valor_pretendido=val_pret,
            valor_atual=val_atual,
            responsavel_identificador=responsavel_id,
            unidade_identificador=unidade_id_str,
            unidade_nome_mapeado=unidade_mapeada,
            meta_identificador=meta_id_str,
            tipo_anotacao=tipo_anotacao,
            projeto=projeto,
            prioridade=prioridade,
            autor=autor,
            link_externo=link_externo,
            campos_extras=extras_dict if extras_dict else None,
            raw_item=item,
        )

    contexts_to_run = req.iteration_contexts if req.iteration_contexts and len(req.iteration_contexts) > 0 else [req.context]

    total_raw = 0
    for c_idx, ctx in enumerate(contexts_to_run):
        raw_data = req.raw_data if (c_idx == 0 and req.raw_data is not None) else None
        if raw_data is None:
            if not req.url_base:
                if len(contexts_to_run) == 1:
                    return PreviewMappingResponse(
                        success=False,
                        tipo_integracao=req.tipo_integracao,
                        total_raw_items=0,
                        preview_items=[],
                        warnings_or_errors=["Informe 'raw_data' ou 'url_base' para simular a transformação."]
                    )
                continue
            try:
                status_code, _, data, _, _ = await execute_integrated_request(
                    url_base=req.url_base,
                    path=req.path,
                    metodo_http=req.metodo_http,
                    tipo_autenticacao=req.tipo_autenticacao,
                    auth_endpoint_path=req.auth_endpoint_path,
                    auth_metodo_http=req.auth_metodo_http,
                    auth_headers=req.auth_headers,
                    auth_payload=req.auth_payload,
                    auth_token_path=req.auth_token_path,
                    auth_static_config=req.auth_static_config,
                    headers_padrao=req.headers_padrao,
                    headers_custom=req.headers_custom,
                    parametros_config=req.parametros_config,
                    corpo_requisicao=req.corpo_requisicao,
                    context=ctx,
                )
                if not (200 <= status_code < 300):
                    warnings.append(f"Contexto #{c_idx+1} retornou status HTTP {status_code}: {str(data)[:150]}")
                    continue
                raw_data = data
            except Exception as e:
                warnings.append(f"Contexto #{c_idx+1} falhou: {str(e)}")
                continue

        items = extract_items_by_path(raw_data, map_cfg.items_root_path)
        if isinstance(items, list):
            total_raw += len(items)
            for i_idx, item in enumerate(items[:50]):
                t_item = transform_single_item(item, total_raw, ctx)
                if t_item:
                    ext_key = str(t_item.external_id or f"item-{len(transformed)}")
                    if ext_key in transformed_dict:
                        transformed_dict[ext_key].quantidade_registros += 1
                    else:
                        t_item.quantidade_registros = 1
                        transformed_dict[ext_key] = t_item

    transformed = list(transformed_dict.values())

    return PreviewMappingResponse(
        success=True,
        tipo_integracao=req.tipo_integracao,
        total_raw_items=total_raw if total_raw > 0 else len(transformed),
        preview_items=transformed,
        warnings_or_errors=warnings
    )
