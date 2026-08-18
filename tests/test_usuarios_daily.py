import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.atribuicao import Atribuicao
from app.models.diario_config import DiarioConfig
from app.models.diario_item import DiarioItem
from app.models.diario_item_anotacao import DiarioItemAnotacao
from app.models.enums import NivelCodigoEnum, TipoDiarioItemAnotacaoEnum, TipoNivelEnum
from app.models.grupo import GrupoTrabalho
from app.models.nivel import Nivel
from app.models.organizacao import Organizacao
from app.models.unidade import Unidade
from app.models.usuario import Usuario
from app.models.usuario_organizacao import UsuarioOrganizacao
from app.services import auth_service, usuario_service

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_get_user_daily_notes(db):
    # 1. Setup Níveis
    nivel_part = Nivel(valor=NivelCodigoEnum.PARTICIPANTE.value, nome="Participante", tipo=TipoNivelEnum.ATRIBUICAO)
    db.add(nivel_part)
    db.commit()

    # 2. Setup Organização, Unidade e Grupo
    org = Organizacao(nome="Org Teste", sigla="OT")
    db.add(org)
    db.commit()

    unidade = Unidade(nome="Unidade Teste", sigla="UT", id_organizacao=org.id)
    db.add(unidade)
    db.commit()

    grupo = GrupoTrabalho(nome="Grupo Teste", id_unidade=unidade.id, id_organizacao=org.id)
    db.add(grupo)
    db.commit()

    config = DiarioConfig(id_grupo=grupo.id, periodo_addnota_inicio="08:00", periodo_addnota_fim="18:00")
    db.add(config)
    db.commit()

    # 3. Setup Usuário e Atribuição
    user = Usuario(
        usuario="membro1",
        nome="Membro Um",
        email="membro1@teste.com",
        senha=auth_service.get_password_hash("password123"),
        is_autorizado=True,
        inativo=False,
    )
    db.add(user)
    db.commit()

    db.add(UsuarioOrganizacao(id_usuario=user.id, id_organizacao=org.id, inativo=False))
    atrib = Atribuicao(id_usuario=user.id, id_grupo=grupo.id, id_nivel=nivel_part.id, inativo=False)
    db.add(atrib)
    db.commit()

    # 4. Setup Daily Item e Anotações
    today = date.today()
    item = DiarioItem(id_diario_config=config.id, id_atribuicao_usuario=atrib.id, data_diario=today, inativo=False)
    db.add(item)
    db.commit()

    anotacao1 = DiarioItemAnotacao(
        id_diario_item=item.id,
        tipo=TipoDiarioItemAnotacaoEnum.TODAY,
        descricao="Desenvolver nova funcionalidade",
        inativo=False
    )
    anotacao2 = DiarioItemAnotacao(
        id_diario_item=item.id,
        tipo=TipoDiarioItemAnotacaoEnum.IMPEDIMENT,
        descricao="Aguardando liberação de acesso",
        inativo=False
    )
    db.add_all([anotacao1, anotacao2])
    db.commit()

    # 5. Query user daily notes
    notes = usuario_service.get_user_daily_notes(db, user.id, dias=30, id_organizacao=org.id)
    assert len(notes) == 2
    descricoes = [n["conteudo"] for n in notes]
    assert "Desenvolver nova funcionalidade" in descricoes
    assert "Aguardando liberação de acesso" in descricoes
    assert notes[0]["grupo_nome"] == "Grupo Teste"
    assert notes[0]["unidade_sigla"] == "UT"
