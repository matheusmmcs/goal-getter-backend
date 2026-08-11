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


