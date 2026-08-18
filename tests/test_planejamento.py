import pytest
from datetime import date
from uuid import uuid4
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.core.database import Base, get_db
from app.main import app
from app.models.enums import MetaStatusEnum, EntregaStatusEnum, OrigemPlanejamentoEnum, OrigemEntregaEnum, PapelOrganizacaoEnum
from app.models.usuario import Usuario
from app.models.organizacao import Organizacao
from app.models.usuario_organizacao import UsuarioOrganizacao
from app.models.unidade import Unidade
from app.models.meta import Meta
from app.models.entrega import Entrega
from app.schemas.planejamento import MetaCreate, MetaUpdate, EntregaCreate, EntregaUpdate
from app.services import meta_service, entrega_service
from app.core.config import settings
from jose import jwt

from sqlalchemy.pool import StaticPool

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)



@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def setup_org_and_user(db):
    user = Usuario(
        usuario="gestor_teste",
        senha="hashed_pass",
        nome="Gestor Teste",
        email="gestor@ufpi.br",
        is_admin=False,
        is_autorizado=True,
        ativo=True,
        inativo=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    org = Organizacao(
        nome="Org Planejamento Teste",
        sigla="ORG-PLAN",
        ativo=True,
        inativo=False
    )
    db.add(org)
    db.commit()
    db.refresh(org)

    vinculo = UsuarioOrganizacao(
        id_usuario=user.id,
        id_organizacao=org.id,
        papel_organizacao=PapelOrganizacaoEnum.GESTOR,
        ativo=True,
        inativo=False
    )
    db.add(vinculo)

    unidade = Unidade(
        nome="Núcleo de Tecnologia da Informação",
        sigla="NTI",
        id_organizacao=org.id,
        ativo=True,
        inativo=False
    )
    db.add(unidade)
    db.commit()
    db.refresh(unidade)

    return {"user": user, "org": org, "unidade": unidade}


def test_meta_crud_and_progress_calculation(db, setup_org_and_user):
    org = setup_org_and_user["org"]
    unidade = setup_org_and_user["unidade"]

    # 1. Create Meta with quantitative target
    data = MetaCreate(
        titulo="Modernização da Infraestrutura Cloud",
        descricao="Migração dos sistemas legados",
        codigo="META-2026-01",
        valor_meta_inicial=0.0,
        valor_meta_pretendida=100.0,
        valor_meta_atual=25.0,
        data_inicio=date(2026, 1, 1),
        data_fim=date(2026, 12, 31),
        status=MetaStatusEnum.EM_ANDAMENTO,
        tipo_origem=OrigemPlanejamentoEnum.INTERNA,
        id_unidade=unidade.id
    )

    created_meta = meta_service.create(db, org.id, data)
    assert created_meta.id is not None
    assert created_meta.titulo == "Modernização da Infraestrutura Cloud"
    assert created_meta.valor_meta_atual == 25.0
    assert created_meta.progresso_percentual == 25.0
    assert created_meta.unidade_nome == "Núcleo de Tecnologia da Informação"

    # 2. Update valor_meta_atual
    update_data = MetaUpdate(valor_meta_atual=75.0)
    updated_meta = meta_service.update(db, org.id, created_meta.id, update_data)
    assert updated_meta.valor_meta_atual == 75.0
    assert updated_meta.progresso_percentual == 75.0

    # 3. List metas with search query
    list_res = meta_service.list_all(db, org.id, q="Infraestrutura")
    assert list_res["total"] == 1
    assert len(list_res["items"]) == 1

    # 4. Deactivate meta
    meta_service.deactivate(db, org.id, created_meta.id)
    list_after = meta_service.list_all(db, org.id)
    assert list_after["total"] == 0


def test_entrega_crud_and_summary_by_unit(db, setup_org_and_user):
    org = setup_org_and_user["org"]
    unidade = setup_org_and_user["unidade"]
    user = setup_org_and_user["user"]

    # Create Meta first
    meta_data = MetaCreate(
        titulo="Meta de Serviços Digitais",
        valor_meta_inicial=0.0,
        valor_meta_pretendida=0.0,
        valor_meta_atual=0.0,
        status=MetaStatusEnum.EM_ANDAMENTO,
        tipo_origem=OrigemPlanejamentoEnum.INTERNA,
        id_unidade=unidade.id
    )
    meta = meta_service.create(db, org.id, meta_data)

    # 1. Create Internal Entrega
    entrega_interna = entrega_service.create(
        db,
        org.id,
        EntregaCreate(
            id_meta=meta.id,
            id_unidade=unidade.id,
            id_usuario_responsavel=user.id,
            titulo="Desenvolver API de Autenticação",
            descricao="Implementação do módulo OAuth2",
            tipo_origem=OrigemEntregaEnum.INTERNA,
            status=EntregaStatusEnum.EM_ANDAMENTO,
            progresso_percentual=50
        )
    )
    assert entrega_interna.id is not None
    assert entrega_interna.tipo_origem == OrigemEntregaEnum.INTERNA
    assert entrega_interna.meta_titulo == "Meta de Serviços Digitais"
    assert entrega_interna.usuario_responsavel_nome == "Gestor Teste"

    # 2. Create External Entrega (with external_id)
    entrega_externa = entrega_service.create(
        db,
        org.id,
        EntregaCreate(
            id_meta=meta.id,
            id_unidade=unidade.id,
            external_id="PETRVS-2026-9999",
            titulo="Entrega Sincronizada do Petrvs",
            tipo_origem=OrigemEntregaEnum.EXTERNA,
            status=EntregaStatusEnum.ENTREGUE,
            progresso_percentual=100
        )
    )
    assert entrega_externa.external_id == "PETRVS-2026-9999"
    assert entrega_externa.tipo_origem == OrigemEntregaEnum.EXTERNA

    # 3. Create Standalone Entrega (without id_meta - opcional)
    entrega_avulsa = entrega_service.create(
        db,
        org.id,
        EntregaCreate(
            id_meta=None,
            id_unidade=unidade.id,
            titulo="Entrega Avulsa Sem Meta",
            tipo_origem=OrigemEntregaEnum.INTERNA,
            status=EntregaStatusEnum.EM_ANDAMENTO,
            progresso_percentual=20
        )
    )
    assert entrega_avulsa.id is not None
    assert entrega_avulsa.id_meta is None
    assert entrega_avulsa.meta_titulo is None

    # 4. Test list_resumo_by_unidade (for daily standup selector)
    resumo_list = entrega_service.list_resumo_by_unidade(db, org.id, unidade.id)
    assert len(resumo_list) == 3
    titulos = [r.titulo for r in resumo_list]
    assert "Desenvolver API de Autenticação" in titulos
    assert "Entrega Sincronizada do Petrvs" in titulos
    assert "Entrega Avulsa Sem Meta" in titulos

    # 5. Check that Meta progress is calculated based on delivered items linked to this meta (1 out of 2 = 50%)
    meta_info = meta_service.get_by_id(db, org.id, meta.id)
    assert meta_info.total_entregas == 2
    assert meta_info.total_entregas_concluidas == 1
    assert meta_info.progresso_percentual == 50.0

    # 6. Deactivate Entrega
    entrega_service.deactivate(db, org.id, entrega_interna.id)
    resumo_after = entrega_service.list_resumo_by_unidade(db, org.id, unidade.id)
    assert len(resumo_after) == 2



def test_api_endpoints_tenant_isolation(db, setup_org_and_user):
    user = setup_org_and_user["user"]
    org = setup_org_and_user["org"]
    unidade = setup_org_and_user["unidade"]

    # Generate JWT token for user
    token = jwt.encode({"sub": str(user.id)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    try:
        # Create a Meta via API
        response = client.post(
            "/api/metas/",
            json={
                "titulo": "Meta Endpoint Test",
                "descricao": "Teste via endpoint REST",
                "valor_meta_inicial": 10.0,
                "valor_meta_pretendida": 50.0,
                "valor_meta_atual": 30.0,
                "id_unidade": str(unidade.id),
                "status": "EM_ANDAMENTO",
                "tipo_origem": "INTERNA"
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-Organization-Id": str(org.id)
            }
        )
        assert response.status_code == 200
        data = response.json()["data"]
        meta_id = data["id"]
        assert data["titulo"] == "Meta Endpoint Test"

        # Try to access with random other Organization ID (Tenant Hopping Protection)
        other_org_id = str(uuid4())
        forbidden_response = client.get(
            f"/api/metas/{meta_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Organization-Id": other_org_id
            }
        )
        assert forbidden_response.status_code in (403, 404)

        # Create Entrega via API
        entrega_resp = client.post(
            "/api/entregas/",
            json={
                "id_meta": meta_id,
                "id_unidade": str(unidade.id),
                "titulo": "Entrega Endpoint Test",
                "tipo_origem": "INTERNA",
                "status": "NAO_INICIADA",
                "progresso_percentual": 0
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-Organization-Id": str(org.id)
            }
        )
        assert entrega_resp.status_code == 200
        entrega_id = entrega_resp.json()["data"]["id"]

        # List resumo for unit
        resumo_resp = client.get(
            f"/api/entregas/resumo-unidade?id_unidade={unidade.id}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Organization-Id": str(org.id)
            }
        )
        assert resumo_resp.status_code == 200
        assert len(resumo_resp.json()["data"]) >= 1

    finally:
        app.dependency_overrides.clear()
