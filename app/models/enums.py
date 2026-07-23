import enum

class TipoNivelEnum(str, enum.Enum):
    ATRIBUICAO = 'ATRIBUICAO'
    PERFIL = 'PERFIL'

class TipoDiarioItemAnotacaoEnum(str, enum.Enum):
    TODAY = 'TODAY'
    YESTERDAY = 'YESTERDAY'
    IMPEDIMENT = 'IMPEDIMENT'
