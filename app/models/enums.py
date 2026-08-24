import enum

class TipoNivelEnum(str, enum.Enum):
    ATRIBUICAO = 'ATRIBUICAO'
    PERFIL = 'PERFIL'

class TipoDiarioItemAnotacaoEnum(str, enum.Enum):
    TODAY = 'TODAY'
    YESTERDAY = 'YESTERDAY'
    IMPEDIMENT = 'IMPEDIMENT'

class PapelOrganizacaoEnum(str, enum.Enum):
    GESTOR = 'GESTOR'
    MEMBRO = 'MEMBRO'

class NivelCodigoEnum(int, enum.Enum):
    CHEFE_UNIDADE = 101
    GESTOR_GRUPO = 201
    PARTICIPANTE = 202

class MetaStatusEnum(str, enum.Enum):
    PLANEJADA = 'PLANEJADA'
    EM_ANDAMENTO = 'EM_ANDAMENTO'
    CONCLUIDA = 'CONCLUIDA'
    CANCELADA = 'CANCELADA'

class OrigemPlanejamentoEnum(str, enum.Enum):
    INTERNA = 'INTERNA'
    EXTERNA = 'EXTERNA'

class OrigemEntregaEnum(str, enum.Enum):
    INTERNA = 'INTERNA'
    EXTERNA = 'EXTERNA'

class EntregaStatusEnum(str, enum.Enum):
    NAO_INICIADA = 'NAO_INICIADA'
    EM_ANDAMENTO = 'EM_ANDAMENTO'
    ENTREGUE = 'ENTREGUE'
    ATRASADA = 'ATRASADA'
    CANCELADA = 'CANCELADA'


class TipoIntegracaoEnum(str, enum.Enum):
    RECEBER_METAS = 'RECEBER_METAS'
    RECEBER_ENTREGAS = 'RECEBER_ENTREGAS'
    RECEBER_TAREFAS = 'RECEBER_TAREFAS'
    ENVIAR_NOTAS_TAREFAS = 'ENVIAR_NOTAS_TAREFAS'


class StatusIntegracaoEnum(str, enum.Enum):
    RASCUNHO = 'RASCUNHO'
    ATIVO = 'ATIVO'
    INATIVO = 'INATIVO'


class ModoExecucaoEnum(str, enum.Enum):
    MANUAL_PAINEL = 'MANUAL_PAINEL'
    AGENDADO_CRON = 'AGENDADO_CRON'
    GLOBAL_UNICO = 'GLOBAL_UNICO'
    POR_UNIDADE = 'POR_UNIDADE'
    POR_USUARIO = 'POR_USUARIO'
    AUTOMATICO = 'AUTOMATICO'
    BOTAO_NA_FUNCIONALIDADE = 'BOTAO_NA_FUNCIONALIDADE'


class EntidadeCampoCustomizadoEnum(str, enum.Enum):
    USUARIO = 'USUARIO'
    UNIDADE = 'UNIDADE'


class TipoDadoCampoCustomizadoEnum(str, enum.Enum):
    TEXTO = 'TEXTO'
    NUMERO = 'NUMERO'
    BOOLEANO = 'BOOLEANO'


class EscopoIteracaoEnum(str, enum.Enum):
    TODAS = 'TODAS'
    SELECIONADAS = 'SELECIONADAS'
    TODOS = 'TODOS'
    SELECIONADOS = 'SELECIONADOS'
    USUARIO_LOGADO = 'USUARIO_LOGADO'


class ProvedorIntegracaoEnum(str, enum.Enum):
    CUSTOM_REST = 'CUSTOM_REST'
    PETRVS = 'PETRVS'
    REDMINE = 'REDMINE'
    JIRA = 'JIRA'
    GLPI = 'GLPI'


class MetodoHttpEnum(str, enum.Enum):
    GET = 'GET'
    POST = 'POST'


class TipoAutenticacaoEnum(str, enum.Enum):
    NONE = 'NONE'
    BEARER_TOKEN = 'BEARER_TOKEN'
    API_KEY_HEADER = 'API_KEY_HEADER'
    API_KEY_QUERY = 'API_KEY_QUERY'
    BASIC_AUTH = 'BASIC_AUTH'
    CUSTOM_HEADER = 'CUSTOM_HEADER'
    DYNAMIC_LOGIN = 'DYNAMIC_LOGIN'


class ParametroLocalizacaoEnum(str, enum.Enum):
    QUERY = 'QUERY'
    PATH = 'PATH'
    HEADER = 'HEADER'
    BODY = 'BODY'


class ParametroTipoOrigemEnum(str, enum.Enum):
    FIXO = 'FIXO'
    VARIAVEL_SISTEMA = 'VARIAVEL_SISTEMA'
    DINAMICO_UNIDADE = 'DINAMICO_UNIDADE'
    DINAMICO_USUARIO = 'DINAMICO_USUARIO'


class StatusExecucaoEnum(str, enum.Enum):
    EM_ANDAMENTO = 'EM_ANDAMENTO'
    SUCESSO = 'SUCESSO'
    PARCIAL = 'PARCIAL'
    FALHA = 'FALHA'


class OrigemDisparoEnum(str, enum.Enum):
    MANUAL = 'MANUAL'
    CRON_AGENDAMENTO = 'CRON_AGENDAMENTO'





