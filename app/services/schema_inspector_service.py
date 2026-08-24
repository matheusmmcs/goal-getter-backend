import time
import re
import json
import base64
import calendar
import urllib.parse
from datetime import datetime, date, timedelta
from typing import Any, Tuple
import httpx

from app.models.enums import (
    MetodoHttpEnum,
    TipoAutenticacaoEnum,
    TipoIntegracaoEnum,
    ParametroLocalizacaoEnum,
    ParametroTipoOrigemEnum,
    ParametroTipoDadoEnum,
    ParametroFormatoDataEnum,
    ParametroFormatoNumeroEnum,
    ParametroFormatoTextoEnum,
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


def format_date_by_pattern(dt: datetime | date, pattern: str) -> str:
    """Formats datetime/date using custom pattern (e.g. YYYY-MM-DD, DD/MM/YYYY, YYYY-MM-DDTHH:mm:ssZ, TIMESTAMP)."""
    if not dt or not pattern:
        return ""
    if not isinstance(dt, datetime):
        dt = datetime.combine(dt, datetime.min.time())

    p_upper = pattern.upper().strip()
    if p_upper in ("TIMESTAMP", "UNIX_TIMESTAMP"):
        return str(int(dt.timestamp()))

    tokens = {
        "YYYY": f"{dt.year:04d}",
        "YY": f"{dt.year % 100:02d}",
        "MM": f"{dt.month:02d}",
        "DD": f"{dt.day:02d}",
        "HH": f"{dt.hour:02d}",
        "mm": f"{dt.minute:02d}",
        "ss": f"{dt.second:02d}",
    }
    return re.sub(r'(YYYY|YY|MM|DD|HH|mm|ss)', lambda m: tokens.get(m.group(0), m.group(0)), pattern)


def format_parameter_value(
    raw_val: Any,
    tipo_dado: str | ParametroTipoDadoEnum | None = None,
    padrao_formatacao: str | None = None,
    formato_data: str | None = None,
    prefixo: str | None = None,
    sufixo: str | None = None,
) -> Any:
    """
    Formats a resolved parameter value according to its data type (DATA, DATA_HORA, NUMERO, TEXTO, BOOLEANO)
    and specified format pattern (e.g. YYYY-MM-DD, YYYY, MM, DD, INTEIRO, DECIMAL_PONTO, DECIMAL_VIRGULA, MAIUSCULO, etc.).
    Supports prefix and suffix wrapping (e.g. '>=2026-08-24').
    """
    if raw_val is None:
        return None
    val_str = str(raw_val).strip()
    if val_str == "":
        return ""

    fmt = padrao_formatacao or formato_data
    t_dado = str(getattr(tipo_dado, "value", tipo_dado)).upper() if tipo_dado else None

    # Check if raw_val has an inline operator prefix like '>=', '<=', '>', '<', '=', '~'
    lead_op = ""
    clean_val = val_str
    if t_dado in ("DATA", "PARAMETROTIPODADOENUM.DATA", "DATE", "DATA_HORA", "PARAMETROTIPODADOENUM.DATA_HORA", "DATETIME"):
        op_match = re.match(r'^([><=!~]+)\s*(.*)$', val_str)
        if op_match:
            lead_op = op_match.group(1)
            clean_val = op_match.group(2)

    result_val = val_str

    # Handle DATA and DATA_HORA
    if t_dado in ("DATA", "PARAMETROTIPODADOENUM.DATA", "DATE"):
        dt = _parse_reference_date(clean_val)
        pattern = fmt or "YYYY-MM-DD"
        result_val = f"{lead_op}{format_date_by_pattern(dt, pattern)}"

    elif t_dado in ("DATA_HORA", "PARAMETROTIPODADOENUM.DATA_HORA", "DATETIME"):
        dt = _parse_reference_date(clean_val)
        pattern = fmt or "YYYY-MM-DDTHH:mm:ssZ"
        result_val = f"{lead_op}{format_date_by_pattern(dt, pattern)}"

    # Handle NUMERO
    elif t_dado in ("NUMERO", "PARAMETROTIPODADOENUM.NUMERO", "NUMBER", "INTEGER", "FLOAT"):
        try:
            cleaned = val_str.replace(" ", "").replace(",", ".")
            num_val = float(cleaned)
            fmt_upper = (fmt or "").upper().strip()
            if fmt_upper in ("INTEIRO", "INTEGER", "INT"):
                result_val = str(int(round(num_val)))
            elif fmt_upper in ("DECIMAL_VIRGULA", "FLOAT_COMMA"):
                result_val = f"{num_val:.2f}".replace(".", ",")
            elif fmt_upper in ("DECIMAL_PONTO", "FLOAT_DOT"):
                result_val = f"{num_val:.2f}"
            else:
                if num_val.is_integer():
                    result_val = str(int(num_val))
                else:
                    result_val = str(num_val)
        except Exception:
            result_val = val_str

    # Handle BOOLEANO
    elif t_dado in ("BOOLEANO", "PARAMETROTIPODADOENUM.BOOLEANO", "BOOLEAN", "BOOL"):
        result_val = "true" if val_str.lower() in ("true", "1", "t", "yes", "sim", "s") else "false"

    # Handle TEXTO (default)
    else:
        if fmt:
            fmt_upper = fmt.upper().strip()
            if fmt_upper in ("MAIUSCULO", "UPPERCASE", "UPPER"):
                result_val = val_str.upper()
            elif fmt_upper in ("MINUSCULO", "LOWERCASE", "LOWER"):
                result_val = val_str.lower()
            elif fmt_upper in ("TRIM", "STRIP"):
                result_val = val_str.strip()
            else:
                result_val = val_str
        else:
            result_val = val_str

    # Apply explicit prefixo / sufixo if specified
    pref = prefixo or ""
    suf = sufixo or ""
    if pref or suf:
        result_val = f"{pref}{result_val}{suf}"

    return result_val


def _apply_date_offset(dt: datetime, offset_expr: str) -> datetime:
    """Applies offset like -1d, -7d, +30d, or special start_of_month/start_of_year."""
    clean = offset_expr.strip().lower()
    if clean in ("inicio_mes", "start_of_month"):
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if clean in ("fim_mes", "end_of_month"):
        _, last_day = calendar.monthrange(dt.year, dt.month)
        return dt.replace(day=last_day, hour=23, minute=59, second=59, microsecond=0)
    if clean in ("inicio_ano", "start_of_year"):
        return dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    m = re.match(r'^([+-]?\d+)\s*([dhmw]?)$', clean)
    if m:
        amount = int(m.group(1))
        unit = m.group(2) or 'd'
        if unit == 'd':
            return dt + timedelta(days=amount)
        elif unit == 'w':
            return dt + timedelta(weeks=amount)
        elif unit == 'h':
            return dt + timedelta(hours=amount)
        elif unit == 'm':
            return dt + timedelta(minutes=amount)
    return dt


def _parse_reference_date(val: Any) -> datetime:
    """Parses reference date string/object or returns current datetime."""
    now = datetime.now()
    if not val:
        return now
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime.combine(val, datetime.min.time())
    if isinstance(val, str):
        clean = val.strip().strip("{}").lower()
        if clean.startswith("data_hoje"):
            offset = clean[len("data_hoje"):]
            return _apply_date_offset(now, offset)
        elif clean.startswith("data_ontem"):
            yesterday = now - timedelta(days=1)
            offset = clean[len("data_ontem"):]
            return _apply_date_offset(yesterday, offset)
        elif clean.startswith("data_referencia") or clean.startswith("data_selecionada") or clean.startswith("data_diario"):
            offset = re.sub(r'^(data_referencia|data_selecionada|data_diario)', '', clean)
            return _apply_date_offset(now, offset)
        elif clean in ("inicio_mes", "start_of_month"):
            return _apply_date_offset(now, "inicio_mes")
        elif clean in ("fim_mes", "end_of_month"):
            return _apply_date_offset(now, "fim_mes")
        elif clean in ("inicio_ano", "start_of_year"):
            return _apply_date_offset(now, "inicio_ano")

        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except Exception:
            pass
        try:
            d = parse_date_safe(val)
            if d:
                return datetime.combine(d, datetime.min.time())
        except Exception:
            pass
    return now


def resolve_template_string(template_str: str, context: dict[str, Any] | None = None) -> str:
    """
    Substitutes template tags in strings. Supports:
    - User/Unit variables & aliases: {user.id}, {id_usuario}, {user.login}, {user.cpf}, {user.email}, {unit.code}, etc.
    - System variables & formats: {ano_atual}, {mes_atual}, {data_hoje}, {data_ontem}, {data_referencia}
    - Direct date format patterns: {YYYY-MM-DD}, {YYYY/MM/DD}, {DD-MM-YYYY}, {DD/MM/YYYY}, {YYYYMMDD}, {YYYY-MM-DDTHH:mm:ssZ}, {TIMESTAMP}
    - Parameterized formats: {data_hoje:YYYY-MM-DD}, {data_referencia:DD/MM/YYYY}, {data_hoje-7d:YYYY-MM-DD}
    - Date arithmetic & relative dates: {data_hoje-1d}, {data_hoje-7d}, {data_hoje-30d}, {inicio_mes}, {fim_mes}, {inicio_ano}
    - Auth tokens: {API_KEY}, {TOKEN}, {BEARER_TOKEN}
    """
    if not template_str:
        return ""

    raw_ctx = dict(context or {})
    now_dt = datetime.now()
    yesterday_dt = now_dt - timedelta(days=1)
    ref_dt = _parse_reference_date(raw_ctx.get("data_referencia") or raw_ctx.get("data_selecionada") or raw_ctx.get("data_diario"))

    default_context = {
        "ano_atual": str(now_dt.year),
        "mes_atual": f"{now_dt.month:02d}",
        "ano": str(now_dt.year),
        "mes": f"{now_dt.month:02d}",
        "data_hoje": now_dt.strftime("%Y-%m-%d"),
        "data_ontem": yesterday_dt.strftime("%Y-%m-%d"),
        "data_referencia": ref_dt.strftime("%Y-%m-%d"),
        "data_selecionada": ref_dt.strftime("%Y-%m-%d"),
        "data_diario": ref_dt.strftime("%Y-%m-%d"),
    }
    merged: dict[str, Any] = {**default_context, **raw_ctx}

    # Aliases de Usuário
    usr_id = merged.get("id_usuario") or merged.get("usuario_id") or merged.get("id_user") or merged.get("user_id")
    if usr_id is not None:
        merged.setdefault("user.id", usr_id)
        merged.setdefault("usuario.id", usr_id)
        merged.setdefault("id_usuario", usr_id)
        merged.setdefault("usuario_id", usr_id)

    usr_login = merged.get("usuario_login") or merged.get("user_login") or merged.get("usuario")
    if usr_login is not None:
        merged.setdefault("user.login", usr_login)
        merged.setdefault("usuario.login", usr_login)
        merged.setdefault("usuario_login", usr_login)

    usr_email = merged.get("usuario_email") or merged.get("user_email") or merged.get("email")
    if usr_email is not None:
        merged.setdefault("user.email", usr_email)
        merged.setdefault("usuario.email", usr_email)
        merged.setdefault("usuario_email", usr_email)

    usr_cpf = merged.get("usuario_cpf") or merged.get("cpf_usuario") or merged.get("cpf")
    if usr_cpf is not None:
        merged.setdefault("user.cpf", usr_cpf)
        merged.setdefault("usuario.cpf", usr_cpf)
        merged.setdefault("usuario_cpf", usr_cpf)

    usr_nome = merged.get("usuario_nome") or merged.get("user_name") or merged.get("nome")
    if usr_nome is not None:
        merged.setdefault("user.name", usr_nome)
        merged.setdefault("user.nome", usr_nome)
        merged.setdefault("usuario.nome", usr_nome)
        merged.setdefault("usuario_nome", usr_nome)

    # Aliases de Unidade
    und_code = merged.get("codigo_unidade") or merged.get("sigla_unidade") or merged.get("sigla") or merged.get("id_unidade")
    if und_code is not None:
        merged.setdefault("unit.code", und_code)
        merged.setdefault("unit.sigla", und_code)
        merged.setdefault("unidade.sigla", und_code)
        merged.setdefault("codigo_unidade", und_code)

    und_id = merged.get("id_unidade") or merged.get("unidade_id")
    if und_id is not None:
        merged.setdefault("unit.id", und_id)
        merged.setdefault("unidade.id", und_id)
        merged.setdefault("id_unidade", und_id)

    und_nome = merged.get("nome_unidade") or merged.get("unidade_nome")
    if und_nome is not None:
        merged.setdefault("unit.name", und_nome)
        merged.setdefault("unidade.nome", und_nome)
        merged.setdefault("nome_unidade", und_nome)

    # Expande automaticamente apelidos para campos customizados
    extra_aliases = {}
    for k, v in list(merged.items()):
        if v is not None:
            if k.startswith("usuario_"):
                short_k = k[len("usuario_"):]
                extra_aliases.setdefault(short_k, v)
                extra_aliases.setdefault(f"user.{short_k}", v)
                extra_aliases.setdefault(f"usuario.{short_k}", v)
            elif k.startswith("user."):
                short_k = k[len("user."):]
                extra_aliases.setdefault(short_k, v)
                extra_aliases.setdefault(f"usuario_{short_k}", v)
                extra_aliases.setdefault(f"usuario.{short_k}", v)
            elif k.startswith("unidade_"):
                short_k = k[len("unidade_"):]
                extra_aliases.setdefault(short_k, v)
                extra_aliases.setdefault(f"unit.{short_k}", v)
                extra_aliases.setdefault(f"unidade.{short_k}", v)
            elif k.startswith("unit."):
                short_k = k[len("unit."):]
                extra_aliases.setdefault(short_k, v)
                extra_aliases.setdefault(f"unidade_{short_k}", v)
                extra_aliases.setdefault(f"unidade.{short_k}", v)
    merged.update(extra_aliases)

    # Known direct format patterns and date arithmetic tokens
    direct_date_formats = {
        "YYYY-MM-DD",
        "YYYY/MM/DD",
        "DD-MM-YYYY",
        "DD/MM/YYYY",
        "YYYYMMDD",
        "YYYY-MM-DDTHH:mm:ss",
        "YYYY-MM-DDTHH:mm:ssZ",
        "YYYY-MM",
        "TIMESTAMP",
        "UNIX_TIMESTAMP",
    }

    # Callback to resolve each {tag}
    def replace_tag_match(match: re.Match) -> str:
        tag = match.group(1).strip()

        # 1. Direct key match in merged context
        if tag in merged and merged[tag] is not None:
            return str(merged[tag])

        # 2. Direct date format pattern (evaluated against reference date)
        if tag in direct_date_formats:
            return format_date_by_pattern(ref_dt, tag)

        # 3. Parameterized format {base_var:format_pattern}
        if ":" in tag:
            base_var, fmt = tag.split(":", 1)
            base_var = base_var.strip()
            fmt = fmt.strip()

            target_dt = None
            if base_var.startswith("data_hoje"):
                offset = base_var[len("data_hoje"):]
                target_dt = _apply_date_offset(now_dt, offset) if offset else now_dt
            elif base_var.startswith("data_ontem"):
                offset = base_var[len("data_ontem"):]
                target_dt = _apply_date_offset(yesterday_dt, offset) if offset else yesterday_dt
            elif base_var.startswith("data_referencia") or base_var.startswith("data_selecionada") or base_var.startswith("data_diario"):
                offset = re.sub(r'^(data_referencia|data_selecionada|data_diario)', '', base_var)
                target_dt = _apply_date_offset(ref_dt, offset) if offset else ref_dt
            elif base_var in ("inicio_mes", "start_of_month"):
                target_dt = _apply_date_offset(ref_dt, "inicio_mes")
            elif base_var in ("fim_mes", "end_of_month"):
                target_dt = _apply_date_offset(ref_dt, "fim_mes")
            elif base_var in ("inicio_ano", "start_of_year"):
                target_dt = _apply_date_offset(ref_dt, "inicio_ano")
            elif base_var in merged and merged[base_var] is not None:
                target_dt = _parse_reference_date(merged[base_var])

            if target_dt is not None:
                return format_date_by_pattern(target_dt, fmt)

        # 4. Date arithmetic tokens without explicit format (defaults to YYYY-MM-DD)
        if tag.startswith("data_hoje") and len(tag) > len("data_hoje"):
            offset = tag[len("data_hoje"):]
            target_dt = _apply_date_offset(now_dt, offset)
            return target_dt.strftime("%Y-%m-%d")
        if tag.startswith("data_referencia") and len(tag) > len("data_referencia"):
            offset = tag[len("data_referencia"):]
            target_dt = _apply_date_offset(ref_dt, offset)
            return target_dt.strftime("%Y-%m-%d")
        if tag in ("inicio_mes", "start_of_month"):
            return _apply_date_offset(ref_dt, "inicio_mes").strftime("%Y-%m-%d")
        if tag in ("fim_mes", "end_of_month"):
            return _apply_date_offset(ref_dt, "fim_mes").strftime("%Y-%m-%d")
        if tag in ("inicio_ano", "start_of_year"):
            return _apply_date_offset(ref_dt, "inicio_ano").strftime("%Y-%m-%d")

        # Tag not found in context - keep as is or blank if empty
        return match.group(0)

    # Perform replacement on all {placeholder} occurrences
    result = re.sub(r'\{([^{}]+)\}', replace_tag_match, template_str)
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
) -> Tuple[int, float, Any, dict[str, str], str | None, str]:
    """Executes full integrated HTTP request resolving parameters, path tags, headers, and dynamic auth."""
    ctx = dict(context or {})

    # 1. Inject static auth keys/tokens into resolution context
    if auth_static_config and isinstance(auth_static_config, dict):
        key_val = (
            auth_static_config.get("api_key")
            or auth_static_config.get("param_value")
            or auth_static_config.get("key")
            or auth_static_config.get("token")
            or auth_static_config.get("bearer_token")
            or auth_static_config.get("header_value")
        )
        if key_val:
            ctx.setdefault("API_KEY", str(key_val))
            ctx.setdefault("api_key", str(key_val))
            ctx.setdefault("TOKEN", str(key_val))
            ctx.setdefault("token", str(key_val))
            ctx.setdefault("BEARER_TOKEN", str(key_val))
            ctx.setdefault("bearer_token", str(key_val))

    # 2. Build auth & headers (obtains dynamic auth token if configured)
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
    if dynamic_token:
        ctx.setdefault("TOKEN", str(dynamic_token))
        ctx.setdefault("token", str(dynamic_token))
        ctx.setdefault("API_KEY", str(dynamic_token))
        ctx.setdefault("api_key", str(dynamic_token))
        ctx.setdefault("BEARER_TOKEN", str(dynamic_token))
        ctx.setdefault("bearer_token", str(dynamic_token))

    # 3. Resolve path template and join url
    resolved_path = resolve_template_string(path, ctx)
    full_url = join_url(url_base, resolved_path)

    if not is_safe_url(full_url):
        raise ValueError(f"URL de destino inválida: {full_url}")

    # 4. Process parameters
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
            if p.tipo_origem == ParametroTipoOrigemEnum.INFORMADO_USUARIO:
                # Runtime parameter: check if explicitly passed in context
                val = ctx.get(p.nome) if ctx else None
                if val is None or val == "":
                    if p.valor_padrao:
                        val = resolve_template_string(p.valor_padrao, ctx)
                    else:
                        val = ""
            else:
                tmpl = p.valor_template
                # If tmpl is empty, resolve based on tipo_origem / tipo_dado
                if not tmpl:
                    if p.tipo_origem == ParametroTipoOrigemEnum.VARIAVEL_SISTEMA:
                        t_dado = getattr(p, "tipo_dado", None)
                        t_dado_str = str(t_dado.value if hasattr(t_dado, "value") else t_dado).upper() if t_dado else ""
                        if t_dado_str in ("DATA", "DATA_HORA"):
                            tmpl = "{data_hoje}"
                        else:
                            tmpl = f"{{{p.nome}}}"
                    else:
                        tmpl = f"{{{p.nome}}}"

                val = resolve_template_string(tmpl, ctx)
                if (val is None or val == "" or val == f"{{{p.nome}}}"):
                    if p.valor_padrao:
                        val = resolve_template_string(p.valor_padrao, ctx)
                    elif val == f"{{{p.nome}}}":
                        val = ""

            # Apply type and pattern formatting + prefix/suffix
            tipo_dado = getattr(p, "tipo_dado", None)
            padrao = getattr(p, "padrao_formatacao", None) or getattr(p, "formato_data", None)
            pref = getattr(p, "prefixo", None)
            suf = getattr(p, "sufixo", None)
            if val is not None and val != "":
                val = format_parameter_value(val, tipo_dado, padrao, prefixo=pref, sufixo=suf)

            if p.obrigatorio and (val is None or val == ""):
                raise ValueError(f"Parâmetro obrigatório '{p.nome}' não pôde ser resolvido com o contexto fornecido.")

            loc = p.localizacao
            if loc == ParametroLocalizacaoEnum.QUERY:
                query_params[p.nome] = val
            elif loc == ParametroLocalizacaoEnum.HEADER:
                headers[p.nome] = str(val) if val is not None else ""
            elif loc == ParametroLocalizacaoEnum.PATH:
                full_url = full_url.replace(f"{{{p.nome}}}", urllib.parse.quote(str(val) if val is not None else ""))

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
    executed_url = str(resp.request.url)

    try:
        parsed_data = resp.json()
    except Exception:
        parsed_data = {"raw_text": resp.text[:2000]}

    return resp.status_code, latency_ms, parsed_data, resp_headers, dynamic_token, executed_url


async def test_connection(req: TestConnectionRequest) -> TestConnectionResponse:
    """Tests connection to URL_INTEGRACAO base and verifies authentication."""
    try:
        status_code, latency_ms, data, headers_ret, token, executed_url = await execute_integrated_request(
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
            executed_url=executed_url,
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
    last_executed_url = None
    last_status_code = None

    if payload is None:
        contexts_to_run = req.iteration_contexts if req.iteration_contexts and len(req.iteration_contexts) > 0 else [req.context]
        all_payloads = []
        errors = []
        latencies = []

        for c_idx, ctx in enumerate(contexts_to_run):
            try:
                status_code, lat, data, _, _, exec_url = await execute_integrated_request(
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
                last_executed_url = exec_url
                last_status_code = status_code
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
                status_code=last_status_code,
                executed_method=req.metodo_http.value if hasattr(req.metodo_http, "value") else str(req.metodo_http),
                executed_url=last_executed_url,
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
        status_code=last_status_code or 200,
        executed_method=req.metodo_http.value if hasattr(req.metodo_http, "value") else str(req.metodo_http),
        executed_url=last_executed_url,
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
    extracted_values = [str(extract_field_value(item, p) or "") for p in (paths or [])]
    if template:
        res = template
        for i, val in enumerate(extracted_values):
            res = res.replace(f"{{{i}}}", val)
        for p, val in zip(paths, extracted_values):
            clean_p = p.replace('.', '_')
            res = res.replace(f"{{{clean_p}}}", val)
            res = res.replace(f"{{{p}}}", val)
        return res
    return "-".join(extracted_values)


def resolve_item_url_template(template_or_field: str | None, item: dict[str, Any]) -> str | None:
    """
    Resolves external link either from a single field path (e.g. 'html_url', 'url')
    or by interpolating a parameterized template string with item fields
    (e.g. 'https://redminedes.ufpi.br/{project.id}/{id}/view').
    """
    if not template_or_field or not isinstance(item, dict):
        return None
    cleaned = template_or_field.strip()
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
        status_map_dict = dict(map_cfg.map_status_values or {})
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
        campos_extras = getattr(map_cfg, "campos_extras", None) or map_cfg.campos_extras
        if campos_extras:
            for extra_item in (campos_extras or []):
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
    last_executed_url = None
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
                        warnings_or_errors=["Informe 'raw_data' ou 'url_base' para simular a transformação."],
                        executed_url=None,
                    )
                continue
            try:
                status_code, _, data, _, _, exec_url = await execute_integrated_request(
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
                last_executed_url = exec_url
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
        warnings_or_errors=warnings,
        executed_url=last_executed_url,
    )
