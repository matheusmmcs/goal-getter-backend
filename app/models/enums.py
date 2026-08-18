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



