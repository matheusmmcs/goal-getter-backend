from datetime import datetime, date
from uuid import UUID
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.enums import (
    TipoIntegracaoEnum,
    ProvedorIntegracaoEnum,
    MetodoHttpEnum,
    TipoAutenticacaoEnum,
    ModoExecucaoEnum,
    ParametroLocalizacaoEnum,
    ParametroTipoOrigemEnum,
    StatusExecucaoEnum,
    OrigemDisparoEnum,
    EntregaStatusEnum,
    MetaStatusEnum,
)


# ==========================================
# PARÂMETROS E DE-PARA SCHEMAS
# ==========================================

class ParametroConfigSchema(BaseModel):
    nome: str = Field(..., description="Nome da chave do parâmetro")
    localizacao: ParametroLocalizacaoEnum = Field(ParametroLocalizacaoEnum.QUERY, description="Onde o parâmetro é injetado: QUERY, PATH, HEADER ou BODY")
    tipo_origem: ParametroTipoOrigemEnum = Field(ParametroTipoOrigemEnum.FIXO, description="Origem do valor: FIXO, VARIAVEL_SISTEMA, DINAMICO_UNIDADE ou DINAMICO_USUARIO")
    valor_template: str = Field(..., description="Valor fixo ou template com tags ex: '{ano_atual}', '{codigo_unidade}'")
    obrigatorio: bool = Field(True, description="Se true, a ausência do valor impede o disparo")
    descricao: str | None = None


class DeParaUnidadeItem(BaseModel):
    codigo_externo: str = Field(..., description="Código, sigla ou identificador da unidade na API externa (ex: 'DTI', '102')")
    id_unidade: UUID | None = Field(None, description="ID da unidade correspondente no Goal Getter (se nulo, vincula à organização toda)")
    nome_externo: str | None = None
    parametros: dict[str, Any] | None = Field(None, description="Parâmetros específicos adicionais para esta unidade")


class DeParaUsuarioItem(BaseModel):
    identificador_externo: str = Field(..., description="CPF, e-mail, login ou ID do usuário na API externa")
    id_usuario: UUID = Field(..., description="ID do usuário correspondente no Goal Getter")
    nome_externo: str | None = None
    parametros: dict[str, Any] | None = None


# ==========================================
# MAPEAMENTO SCHEMAS (PONTE LEGO)
# ==========================================

class IntegracaoMapeamentoBase(BaseModel):
    items_root_path: str = Field("$", description="JSON path para o array de itens, ex: '$', 'entregas', 'data.results'")
    external_id_mode: str = Field("SIMPLE", description="'SIMPLE' ou 'COMPOSITE'")
    external_id_path: str | None = Field(None, description="Caminho do campo ID simples, ex: 'id' ou 'codigo'")
    external_id_composite_paths: list[str] | None = Field(None, description="Lista de caminhos para chave composta, ex: ['plano_id', 'codigo']")
    external_id_composite_template: str | None = Field(None, description="Template para interpolação da chave composta, ex: '{plano_id}#{codigo}'")
    campo_titulo: str = Field(..., min_length=1, description="Caminho do título")
    campo_descricao: str | None = None
    campo_codigo: str | None = None
    campo_data_inicio: str | None = None
    campo_data_fim: str | None = None
    campo_data_conclusao: str | None = None
    campo_status: str | None = None
    map_status_values: dict[str, str] | None = Field(None, description="De/Para de status externo -> status canônico Goal Getter")
    campo_progresso: str | None = None
    campo_valor_inicial: str | None = None
    campo_valor_pretendido: str | None = None
    campo_valor_atual: str | None = None
    campo_responsavel: str | None = Field(None, description="Identificador do responsável (CPF, e-mail ou login)")
    campo_tipo_anotacao: str | None = Field(None, description="Campo que indica tipo de tarefa (TODAY, YESTERDAY, IMPEDIMENT)")
    campo_meta_id: str | None = None
    campo_meta_titulo: str | None = None
    campo_unidade_origem: str | None = Field(None, description="Nó do JSON que identifica a unidade externa")
    map_unidades_values: list[DeParaUnidadeItem] | None = None
    map_usuarios_values: list[DeParaUsuarioItem] | None = None
    default_id_meta: UUID | None = None
    default_id_unidade: UUID | None = None
    regras_transformacao: dict[str, Any] | None = None


class IntegracaoMapeamentoCreate(IntegracaoMapeamentoBase):
    pass


class IntegracaoMapeamentoUpdate(BaseModel):
    items_root_path: str | None = None
    external_id_mode: str | None = None
    external_id_path: str | None = None
    external_id_composite_paths: list[str] | None = None
    external_id_composite_template: str | None = None
    campo_titulo: str | None = None
    campo_descricao: str | None = None
    campo_codigo: str | None = None
    campo_data_inicio: str | None = None
    campo_data_fim: str | None = None
    campo_data_conclusao: str | None = None
    campo_status: str | None = None
    map_status_values: dict[str, str] | None = None
    campo_progresso: str | None = None
    campo_valor_inicial: str | None = None
    campo_valor_pretendido: str | None = None
    campo_valor_atual: str | None = None
    campo_responsavel: str | None = None
    campo_tipo_anotacao: str | None = None
    campo_meta_id: str | None = None
    campo_meta_titulo: str | None = None
    campo_unidade_origem: str | None = None
    map_unidades_values: list[DeParaUnidadeItem] | None = None
    map_usuarios_values: list[DeParaUsuarioItem] | None = None
    default_id_meta: UUID | None = None
    default_id_unidade: UUID | None = None
    regras_transformacao: dict[str, Any] | None = None


class IntegracaoMapeamentoResponse(IntegracaoMapeamentoBase):
    id: UUID
    id_integracao_endpoint: UUID
    default_meta_titulo: str | None = None
    default_unidade_nome: str | None = None
    inativo: bool
    created_at: datetime
    updated_at: datetime | None = None
    ativo: bool

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# ENDPOINTS DE CONSULTA SCHEMAS
# ==========================================

class IntegracaoEndpointBase(BaseModel):
    nome: str = Field(..., min_length=1, max_length=255)
    tipo_integracao: TipoIntegracaoEnum = TipoIntegracaoEnum.RECEBER_ENTREGAS
    path: str = Field(..., description="Caminho relativo a partir da URL_INTEGRACAO, ex: '/metas' ou '/unidades/{codigo_unidade}/entregas'")
    metodo_http: MetodoHttpEnum = MetodoHttpEnum.GET
    modo_execucao: ModoExecucaoEnum = ModoExecucaoEnum.MANUAL_PAINEL
    parametros_config: list[ParametroConfigSchema] | None = None
    headers_custom: dict[str, str] | None = None
    corpo_requisicao: str | None = None
    escopo_unidades: str | None = 'TODAS'
    unidades_selecionadas: list[UUID] | None = None
    escopo_usuarios: str | None = 'TODOS'
    usuarios_selecionados: list[UUID] | None = None
    ativo_sincronizacao: bool = True
    frequencia_cron: str | None = None


class IntegracaoEndpointCreate(IntegracaoEndpointBase):
    mapeamento: IntegracaoMapeamentoCreate | None = None


class IntegracaoEndpointUpdate(BaseModel):
    nome: str | None = Field(None, min_length=1, max_length=255)
    tipo_integracao: TipoIntegracaoEnum | None = None
    path: str | None = None
    metodo_http: MetodoHttpEnum | None = None
    modo_execucao: ModoExecucaoEnum | None = None
    parametros_config: list[ParametroConfigSchema] | None = None
    headers_custom: dict[str, str] | None = None
    corpo_requisicao: str | None = None
    escopo_unidades: str | None = None
    unidades_selecionadas: list[UUID] | None = None
    escopo_usuarios: str | None = None
    usuarios_selecionados: list[UUID] | None = None
    ativo_sincronizacao: bool | None = None
    frequencia_cron: str | None = None
    mapeamento: IntegracaoMapeamentoUpdate | None = None


class IntegracaoEndpointResponse(IntegracaoEndpointBase):
    id: UUID
    id_integracao_config: UUID
    inativo: bool
    created_at: datetime
    updated_at: datetime | None = None
    ativo: bool
    mapeamento: IntegracaoMapeamentoResponse | None = None
    ultima_execucao_status: StatusExecucaoEnum | None = None
    ultima_execucao_data: datetime | None = None
    total_registros_sincronizados: int = 0

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# CONFIGURAÇÃO / CONEXÃO BASE SCHEMAS
# ==========================================

class IntegracaoConfigBase(BaseModel):
    nome: str = Field(..., min_length=1, max_length=255)
    descricao: str | None = None
    provedor: ProvedorIntegracaoEnum = ProvedorIntegracaoEnum.CUSTOM_REST
    url_base: str = Field(..., min_length=1, description="URL_INTEGRACAO base, ex: 'https://api.ufpi.br/v1'")
    tipo_autenticacao: TipoAutenticacaoEnum = TipoAutenticacaoEnum.NONE
    auth_endpoint_path: str | None = Field(None, description="Path relativo de auth, ex: '/auth/login'")
    auth_metodo_http: MetodoHttpEnum | None = MetodoHttpEnum.POST
    auth_headers: dict[str, str] | None = None
    auth_payload: dict[str, Any] | None = None
    auth_token_path: str | None = Field(None, description="Caminho do token na resposta JSON, ex: 'data.token' ou 'access_token'")
    auth_static_config: dict[str, Any] | None = None
    headers_padrao: dict[str, str] | None = None
    ativo_sincronizacao: bool = True
    frequencia_cron: str | None = None


class IntegracaoConfigCreate(IntegracaoConfigBase):
    endpoints: list[IntegracaoEndpointCreate] | None = None


class IntegracaoConfigUpdate(BaseModel):
    nome: str | None = Field(None, min_length=1, max_length=255)
    descricao: str | None = None
    provedor: ProvedorIntegracaoEnum | None = None
    url_base: str | None = None
    tipo_autenticacao: TipoAutenticacaoEnum | None = None
    auth_endpoint_path: str | None = None
    auth_metodo_http: MetodoHttpEnum | None = None
    auth_headers: dict[str, str] | None = None
    auth_payload: dict[str, Any] | None = None
    auth_token_path: str | None = None
    auth_static_config: dict[str, Any] | None = None
    headers_padrao: dict[str, str] | None = None
    ativo_sincronizacao: bool | None = None
    frequencia_cron: str | None = None


class IntegracaoConfigResponse(IntegracaoConfigBase):
    id: UUID
    id_organizacao: UUID
    id_agendamento: UUID | None = None
    inativo: bool
    created_at: datetime
    updated_at: datetime | None = None
    ativo: bool
    endpoints: list[IntegracaoEndpointResponse] = Field(default_factory=list)
    ultima_execucao_status: StatusExecucaoEnum | None = None
    ultima_execucao_data: datetime | None = None
    total_registros_sincronizados: int = 0

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# HISTÓRICO DE EXECUÇÃO SCHEMAS
# ==========================================

class IntegracaoExecucaoHistoricoResponse(BaseModel):
    id: UUID
    id_integracao_config: UUID
    id_integracao_endpoint: UUID | None = None
    endpoint_nome: str | None = None
    data_inicio: datetime
    data_fim: datetime | None = None
    status: StatusExecucaoEnum
    total_encontrados: int
    total_criados: int
    total_atualizados: int
    total_inalterados: int
    total_erros: int
    log_detalhes: dict[str, Any] | None = None
    disparado_por: OrigemDisparoEnum
    id_usuario_executor: UUID | None = None
    usuario_executor_nome: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# SCHEMAS DE FERRAMENTAS & LIVE PREVIEW (LEGO BUILDER)
# ==========================================

class TestConnectionRequest(BaseModel):
    __test__ = False
    url_base: str
    tipo_autenticacao: TipoAutenticacaoEnum = TipoAutenticacaoEnum.NONE
    auth_endpoint_path: str | None = None
    auth_metodo_http: MetodoHttpEnum | None = MetodoHttpEnum.POST
    auth_headers: dict[str, str] | None = None
    auth_payload: dict[str, Any] | None = None
    auth_token_path: str | None = None
    auth_static_config: dict[str, Any] | None = None
    headers_padrao: dict[str, str] | None = None


class TestConnectionResponse(BaseModel):
    __test__ = False
    success: bool
    status_code: int
    latency_ms: float
    message: str
    headers_returned: dict[str, str] | None = None
    auth_token_preview: str | None = None
    sample_preview: Any | None = None


class JsonTreeNode(BaseModel):
    key: str
    path: str
    type: str  # 'object' | 'array' | 'string' | 'number' | 'boolean' | 'null'
    sample_value: Any | None = None
    is_array: bool = False
    children: list["JsonTreeNode"] | None = None


class InspectSchemaRequest(BaseModel):
    url_base: str
    path: str = ""
    endpoint_path: str | None = None
    metodo_http: MetodoHttpEnum = MetodoHttpEnum.GET
    tipo_autenticacao: TipoAutenticacaoEnum = TipoAutenticacaoEnum.NONE
    auth_endpoint_path: str | None = None
    auth_metodo_http: MetodoHttpEnum | None = MetodoHttpEnum.POST
    auth_headers: dict[str, str] | None = None
    auth_payload: dict[str, Any] | None = None
    auth_token_path: str | None = None
    auth_static_config: dict[str, Any] | None = None
    headers_padrao: dict[str, str] | None = None
    headers_custom: dict[str, str] | None = None
    parametros_config: list[ParametroConfigSchema] | None = None
    corpo_requisicao: str | None = None
    raw_sample: Any | None = None
    context: dict[str, Any] | None = None

    @model_validator(mode='before')
    @classmethod
    def resolve_path_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("path") and data.get("endpoint_path"):
                data["path"] = data["endpoint_path"]
        return data


class InspectSchemaResponse(BaseModel):
    success: bool
    latency_ms: float = 0.0
    detected_arrays: list[str] = Field(default_factory=list, description="Lista de caminhos de array detectados como candidatos a items_root_path")
    schema_tree: list[JsonTreeNode] = Field(default_factory=list, description="Árvore de campos para montagem visual do Lego")
    discovered_fields: list[str] = Field(default_factory=list, description="Lista plana de todos os caminhos de propriedades")
    sample_payload: Any | None = None


class PreviewMappingRequest(BaseModel):
    tipo_integracao: TipoIntegracaoEnum = TipoIntegracaoEnum.RECEBER_ENTREGAS
    raw_data: Any | None = None
    url_base: str | None = None
    path: str = ""
    endpoint_path: str | None = None
    metodo_http: MetodoHttpEnum = MetodoHttpEnum.GET
    tipo_autenticacao: TipoAutenticacaoEnum = TipoAutenticacaoEnum.NONE
    auth_endpoint_path: str | None = None
    auth_metodo_http: MetodoHttpEnum | None = MetodoHttpEnum.POST
    auth_headers: dict[str, str] | None = None
    auth_payload: dict[str, Any] | None = None
    auth_token_path: str | None = None
    auth_static_config: dict[str, Any] | None = None
    headers_padrao: dict[str, str] | None = None
    headers_custom: dict[str, str] | None = None
    parametros_config: list[ParametroConfigSchema] | None = None
    corpo_requisicao: str | None = None
    mapeamento: IntegracaoMapeamentoBase
    context: dict[str, Any] | None = None

    @model_validator(mode='before')
    @classmethod
    def resolve_path_alias(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("path") and data.get("endpoint_path"):
                data["path"] = data["endpoint_path"]
        return data


class TransformedItemPreview(BaseModel):
    tipo_integracao: TipoIntegracaoEnum = TipoIntegracaoEnum.RECEBER_ENTREGAS
    external_id: str
    titulo: str
    descricao: str | None = None
    codigo: str | None = None
    data_inicio: date | None = None
    data_fim: date | None = None
    data_conclusao: date | None = None
    status: str
    progresso_percentual: int | None = None
    valor_inicial: float | None = None
    valor_pretendido: float | None = None
    valor_atual: float | None = None
    responsavel_identificador: str | None = None
    unidade_identificador: str | None = None
    unidade_nome_mapeado: str | None = None
    meta_identificador: str | None = None
    tipo_anotacao: str | None = None
    raw_item: dict[str, Any] | None = None


class PreviewMappingResponse(BaseModel):
    success: bool
    tipo_integracao: TipoIntegracaoEnum = TipoIntegracaoEnum.RECEBER_ENTREGAS
    total_raw_items: int
    preview_items: list[TransformedItemPreview]
    warnings_or_errors: list[str] = Field(default_factory=list)


class SyncResultResponse(BaseModel):
    id_historico: UUID
    status: StatusExecucaoEnum
    total_encontrados: int
    total_criados: int
    total_atualizados: int
    total_inalterados: int
    total_erros: int
    tempo_execucao_ms: float
    log_detalhes: dict[str, Any] | None = None


class SyncPreviewItem(BaseModel):
    external_id: str
    titulo: str
    tipo_integracao: TipoIntegracaoEnum
    acao: str  # 'CRIAR', 'ATUALIZAR', 'INALTERADO'
    status: str | None = None
    data_inicio: str | None = None
    data_fim: str | None = None
    usuario_responsavel_nome: str | None = None
    unidade_nome: str | None = None
    progresso_percentual: int | None = None
    detalhes: dict[str, Any] | None = None


class SyncPreviewErrorDetail(BaseModel):
    tipo: str  # 'HTTP_ERROR', 'MISSING_ID', 'MAPPING_ERROR', 'DESCONHECIDO'
    mensagem: str
    contexto: dict[str, Any] | None = None
    item_raw: dict[str, Any] | None = None


class SyncPreviewResponse(BaseModel):
    integracao_id: UUID
    integracao_nome: str
    endpoint_id: UUID | None = None
    endpoint_nome: str | None = None
    total_encontrados: int
    total_novos: int
    total_atualizados: int
    total_inalterados: int
    total_erros: int
    items: list[SyncPreviewItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    motivos_erros: list[SyncPreviewErrorDetail] = Field(default_factory=list)


