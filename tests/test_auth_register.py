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
        nickname="novousuario",
        email="newuser@ufpi.br",
        cpf="123.456.789-01",
        senha="password123"
    )
    user = auth_service.register_user(db, reg_data)
    assert user.id is not None
    assert user.usuario == "newuser"
    assert user.nome == "Novo Usuario Teste"
    assert user.nickname == "novousuario"
    assert user.email == "newuser@ufpi.br"
    assert user.cpf == "12345678901"  # Apenas dígitos numéricos no banco
    assert user.is_admin is False
    assert user.is_autorizado is True
    assert user.inativo is False
    assert user.data_autorizacao is not None
    assert user.data_inativacao is None

    # Test login by username
    from app.schemas.auth import LoginRequest
    res_user = auth_service.authenticate_user(db, "newuser", "password123")
    assert res_user is not None
    assert res_user.id == user.id

    # Test login by email
    res_email = auth_service.authenticate_user(db, "newuser@ufpi.br", "password123")
    assert res_email is not None
    assert res_email.id == user.id


def test_self_registration_duplicate_username(db):
    reg_data1 = UsuarioRegister(
        usuario="dupuser",
        nome="Usuario 1",
        email="dup1@ufpi.br",
        senha="password123"
    )
    auth_service.register_user(db, reg_data1)

    reg_data2 = UsuarioRegister(
        usuario="DupUser",
        nome="Usuario 2",
        email="dup2@ufpi.br",
        senha="password123"
    )
    with pytest.raises(Exception) as exc_info:
        auth_service.register_user(db, reg_data2)
    assert "já está em uso" in str(exc_info.value)


def test_self_registration_duplicate_nickname(db):
    reg_data1 = UsuarioRegister(
        usuario="user1",
        nome="Usuario 1",
        nickname="meunick",
        email="user1@ufpi.br",
        senha="password123"
    )
    auth_service.register_user(db, reg_data1)

    reg_data2 = UsuarioRegister(
        usuario="user2",
        nome="Usuario 2",
        nickname="MEUNICK",
        email="user2@ufpi.br",
        senha="password123"
    )
    with pytest.raises(Exception) as exc_info:
        auth_service.register_user(db, reg_data2)
    assert "Nickname já está em uso" in str(exc_info.value)


def test_self_registration_duplicate_cpf(db):
    reg_data1 = UsuarioRegister(
        usuario="user_cpf1",
        nome="Usuario CPF 1",
        email="cpf1@ufpi.br",
        cpf="111.222.333-44",
        senha="password123"
    )
    auth_service.register_user(db, reg_data1)

    reg_data2 = UsuarioRegister(
        usuario="user_cpf2",
        nome="Usuario CPF 2",
        email="cpf2@ufpi.br",
        cpf="11122233344",
        senha="password123"
    )
    with pytest.raises(Exception) as exc_info:
        auth_service.register_user(db, reg_data2)
    assert "CPF já está cadastrado" in str(exc_info.value)


def test_self_registration_short_password(db):
    reg_data = UsuarioRegister(
        usuario="shortpass",
        nome="Short Pass",
        email="short@ufpi.br",
        senha="123"
    )
    with pytest.raises(Exception) as exc_info:
        auth_service.register_user(db, reg_data)
    assert "mínimo 8 caracteres" in str(exc_info.value)


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


def test_check_username_availability(db):
    # Inicialmente "mariasilva" está livre
    check1 = auth_service.check_username_availability(db, "mariasilva")
    assert check1["available"] is True
    assert check1["suggested"] == "mariasilva"

    # Cadastra "mariasilva"
    auth_service.register_user(db, UsuarioRegister(
        usuario="mariasilva",
        nome="Maria Silva",
        email="maria@ufpi.br",
        senha="password123"
    ))

    # Agora "mariasilva" deve sugerir "mariasilva2"
    check2 = auth_service.check_username_availability(db, "mariasilva")
    assert check2["available"] is False
    assert check2["suggested"] == "mariasilva2"

    # Cadastra "mariasilva2"
    auth_service.register_user(db, UsuarioRegister(
        usuario="mariasilva2",
        nome="Maria Silva Dois",
        email="maria2@ufpi.br",
        senha="password123"
    ))

    # Agora deve sugerir "mariasilva3"
    check3 = auth_service.check_username_availability(db, "mariasilva")
    assert check3["available"] is False
    assert check3["suggested"] == "mariasilva3"

