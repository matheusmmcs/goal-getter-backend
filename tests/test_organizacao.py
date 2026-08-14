import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.models.enums import PapelOrganizacaoEnum
from app.models.usuario import Usuario
from app.models.organizacao import Organizacao
from app.models.usuario_organizacao import UsuarioOrganizacao
from app.schemas.organizacao import OrganizacaoCreate, UsuarioVinculoItem
from app.services import organizacao_service

# In-memory SQLite for testing
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


def test_create_organizacao_and_vinculos(db):
    user1 = Usuario(
        usuario="testuser",
        senha="hashedpassword",
        nome="Test User",
        email="test@ufpi.br",
        is_admin=False,
        is_autorizado=True
    )
    db.add(user1)
    db.commit()
    db.refresh(user1)

    org_data = OrganizacaoCreate(
        nome="Organização Teste UFPI",
        sigla="ORG-TEST",
        descricao="Organização para testes unitários",
        usuarios_vinculos=[
            UsuarioVinculoItem(id_usuario=user1.id, papel_organizacao=PapelOrganizacaoEnum.GESTOR)
        ]
    )

    org = organizacao_service.create_organizacao(db, org_data)

    assert org.id is not None
    assert org.nome == "Organização Teste UFPI"
    assert org.sigla == "ORG-TEST"

    # Verificar detalhe e vinculo
    detail = organizacao_service.get_detail_by_id(db, org.id)
    assert detail["nome"] == "Organização Teste UFPI"
    assert len(detail["usuarios_vinculos"]) == 1
    assert detail["usuarios_vinculos"][0]["papel_organizacao"] == PapelOrganizacaoEnum.GESTOR
    assert detail["usuarios_vinculos"][0]["usuario_nome"] == "Test User"


def test_update_and_deactivate_vinculo(db):
    user1 = Usuario(
        usuario="user2",
        senha="pass",
        nome="User Two",
        is_admin=False,
        is_autorizado=True
    )
    db.add(user1)
    db.commit()

    org_data = OrganizacaoCreate(nome="Org Beta", sigla="OB")
    org = organizacao_service.create_organizacao(db, org_data)

    # Adicionar vínculo como MEMBRO
    vinculo = organizacao_service.adicionar_vinculo_usuario(
        db, org.id, UsuarioVinculoItem(id_usuario=user1.id, papel_organizacao=PapelOrganizacaoEnum.MEMBRO)
    )
    assert vinculo.papel_organizacao == PapelOrganizacaoEnum.MEMBRO

    # Alterar vínculo para GESTOR
    from app.schemas.organizacao import VinculoUpdateSchema
    updated = organizacao_service.atualizar_vinculo_usuario(
        db, org.id, user1.id, VinculoUpdateSchema(papel_organizacao=PapelOrganizacaoEnum.GESTOR)
    )
    assert updated.papel_organizacao == PapelOrganizacaoEnum.GESTOR

    # Desativar vínculo
    organizacao_service.desativar_vinculo_usuario(db, org.id, user1.id)
    detalhes = organizacao_service.listar_usuarios_detalhados_organizacao(db, org.id)
    assert len(detalhes) == 0


def test_strict_multi_tenancy_isolation(db):
    from app.services import unidade_service, grupo_service, usuario_service
    from app.schemas.unidade import UnidadeCreate
    from app.models.unidade import Unidade
    from app.models.grupo import GrupoTrabalho

    # Criar duas organizações distintas
    org1 = organizacao_service.create_organizacao(db, OrganizacaoCreate(nome="Org 1", sigla="O1"))
    org2 = organizacao_service.create_organizacao(db, OrganizacaoCreate(nome="Org 2", sigla="O2"))

    # Criar usuários para Org 1 e Org 2
    u1 = Usuario(usuario="u1", nome="User One", senha="p", is_admin=False, is_autorizado=True)
    u2 = Usuario(usuario="u2", nome="User Two", senha="p", is_admin=False, is_autorizado=True)
    db.add_all([u1, u2])
    db.commit()

    # Vincular u1 à Org 1 e u2 à Org 2
    organizacao_service.adicionar_vinculo_usuario(
        db, org1.id, UsuarioVinculoItem(id_usuario=u1.id, papel_organizacao=PapelOrganizacaoEnum.MEMBRO)
    )
    organizacao_service.adicionar_vinculo_usuario(
        db, org2.id, UsuarioVinculoItem(id_usuario=u2.id, papel_organizacao=PapelOrganizacaoEnum.MEMBRO)
    )

    # Criar unidades em cada organização
    unidade1 = unidade_service.create(
        db,
        UnidadeCreate(nome="Unidade Org 1", nome_ascii="Unidade Org 1", sigla="U1", id_organizacao=org1.id),
        id_organizacao=org1.id
    )
    unidade2 = unidade_service.create(
        db,
        UnidadeCreate(nome="Unidade Org 2", nome_ascii="Unidade Org 2", sigla="U2", id_organizacao=org2.id),
        id_organizacao=org2.id
    )

    # Criar grupos vinculados a cada unidade
    g1 = GrupoTrabalho(nome="Grupo Org 1", id_unidade=unidade1.id, id_organizacao=org1.id)
    g2 = GrupoTrabalho(nome="Grupo Org 2", id_unidade=unidade2.id, id_organizacao=org2.id)
    db.add_all([g1, g2])
    db.commit()

    # 1. Validar listagem de unidades por organização (isolamento estrito)
    res_u_org1 = unidade_service.list_all(db, page=0, size=10, id_organizacao=org1.id)
    assert res_u_org1["count"] == 1
    assert res_u_org1["items"][0].id == unidade1.id

    res_u_org2 = unidade_service.list_all(db, page=0, size=10, id_organizacao=org2.id)
    assert res_u_org2["count"] == 1
    assert res_u_org2["items"][0].id == unidade2.id

    # 2. Validar listagem de grupos por organização (isolamento estrito)
    res_g_org1 = grupo_service.list_all(db, page=0, size=10, id_organizacao=org1.id)
    assert res_g_org1["count"] == 1
    assert res_g_org1["items"][0].id == g1.id

    res_g_org2 = grupo_service.list_all(db, page=0, size=10, id_organizacao=org2.id)
    assert res_g_org2["count"] == 1
    assert res_g_org2["items"][0].id == g2.id

    # 3. Validar listagem de usuários por organização (isolamento estrito)
    res_usr_org1 = usuario_service.list_usuarios(db, page=0, size=10, id_organizacao=org1.id)
    assert res_usr_org1["count"] == 1
    assert res_usr_org1["items"][0].id == u1.id

    res_usr_org2 = usuario_service.list_usuarios(db, page=0, size=10, id_organizacao=org2.id)
    assert res_usr_org2["count"] == 1
    assert res_usr_org2["items"][0].id == u2.id
