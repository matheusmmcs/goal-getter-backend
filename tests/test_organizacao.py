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
