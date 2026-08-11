import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base
from app.models.usuario import Usuario
from app.services import auth_service, usuario_service
from app.schemas.usuario import UsuarioRegister, UsuarioCreate, UsuarioUpdate

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


def test_self_registration_success(db):
    reg_data = UsuarioRegister(
        usuario="newuser",
        nome="Novo Usuario Teste",
        email="newuser@ufpi.br",
        cpf="12345678901",
        senha="password123"
    )
    user = auth_service.register_user(db, reg_data)
    assert user.id is not None
    assert user.usuario == "newuser"
    assert user.nome == "Novo Usuario Teste"
    assert user.is_admin is False
    assert user.is_autorizado is True
    assert user.inativo is False
    assert user.data_autorizacao is not None
    assert user.data_inativacao is None


def test_self_registration_duplicate_username(db):
    reg_data1 = UsuarioRegister(
        usuario="dupuser",
        nome="Usuario 1",
        senha="password123"
    )
    auth_service.register_user(db, reg_data1)

    reg_data2 = UsuarioRegister(
        usuario="DupUser",
        nome="Usuario 2",
        senha="password123"
    )
    with pytest.raises(Exception) as exc_info:
        auth_service.register_user(db, reg_data2)
    assert "já está em uso" in str(exc_info.value)


def test_admin_deactivate_and_reactivate_timestamps(db):
    create_data = UsuarioCreate(
        usuario="user_to_deactivate",
        nome="User Status Test",
        senha="password123",
        is_autorizado=True
    )
    user = usuario_service.create(db, create_data)
    assert user.data_autorizacao is not None
    assert user.data_inativacao is None

    # Deactivate
    deactivated = usuario_service.deactivate(db, user.id)
    assert deactivated.inativo is True
    assert deactivated.data_inativacao is not None

    # Reactivate
    reactivated = usuario_service.reactivate(db, user.id)
    assert reactivated.inativo is False
    assert reactivated.data_inativacao is None
