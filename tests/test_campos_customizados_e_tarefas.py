import pytest
from uuid import uuid4
from unittest.mock import patch, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from jose import jwt

from app.core.database import Base, get_db
from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.models.enums import (
    PapelOrganizacaoEnum,
    TipoIntegracaoEnum,
    ProvedorIntegracaoEnum,
    MetodoHttpEnum,
    TipoAutenticacaoEnum,
    ModoExecucaoEnum,
    ParametroLocalizacaoEnum,
    ParametroTipoOrigemEnum,
    EntidadeCampoCustomizadoEnum,
    TipoDadoCampoCustomizadoEnum,
)
from app.models.usuario import Usuario
from app.models.organizacao import Organizacao
from app.models.usuario_organizacao import UsuarioOrganizacao
from app.models.organizacao_campo_customizado import OrganizacaoCampoCustomizado
from app.models.unidade import Unidade
from app.models.integracao_config import IntegracaoConfig
from app.models.integracao_endpoint import IntegracaoEndpoint
from app.models.integracao_mapeamento import IntegracaoMapeamento


# Setup in-memory SQLite DB
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def create_token_for_user(user_id: str) -> str:
    return create_access_token({"sub": user_id})


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def test_campos_customizados_crud_e_multi_tenancy():
    db = TestingSessionLocal()

    # Create 2 organizations
    org1 = Organizacao(nome="Org 1", sigla="ORG1", inativo=False, ativo=True)
    org2 = Organizacao(nome="Org 2", sigla="ORG2", inativo=False, ativo=True)
    db.add_all([org1, org2])
    db.commit()

    # Create Manager User for Org 1
    gestor = Usuario(nome="Gestor Org1", usuario="gestor1", email="gestor1@ufpi.br", senha="hash", inativo=False, ativo=True, is_autorizado=True)
    membro = Usuario(nome="Membro Org1", usuario="membro1", email="membro1@ufpi.br", senha="hash", inativo=False, ativo=True, is_autorizado=True)
    db.add_all([gestor, membro])
    db.commit()

    db.add(UsuarioOrganizacao(id_usuario=gestor.id, id_organizacao=org1.id, papel_organizacao=PapelOrganizacaoEnum.GESTOR, inativo=False, ativo=True))
    db.add(UsuarioOrganizacao(id_usuario=membro.id, id_organizacao=org1.id, papel_organizacao=PapelOrganizacaoEnum.MEMBRO, inativo=False, ativo=True))
    db.commit()

    token_gestor = create_token_for_user(str(gestor.id))
    token_membro = create_token_for_user(str(membro.id))
    headers_gestor = {"Authorization": f"Bearer {token_gestor}", "X-Organization-Id": str(org1.id)}
    headers_membro = {"Authorization": f"Bearer {token_membro}", "X-Organization-Id": str(org1.id)}

    # 1. Create custom field as Gestor
    res = client.post(
        f"/api/organizacoes/{org1.id}/campos-customizados",
        headers=headers_gestor,
        json={
            "entidade": "USUARIO",
            "nome_campo": "ID do Usuário no Redmine",
            "chave": "redmine_user_id",
            "tipo_dado": "NUMERO",
            "obrigatorio": False,
            "descricao": "ID numérico do usuário no Redmine",
        },
    )
    assert res.status_code == 200, res.text
    campo_data = res.json()["data"]
    assert campo_data["chave"] == "redmine_user_id"
    campo_id = campo_data["id"]

    # 2. List custom fields
    res_list = client.get(f"/api/organizacoes/{org1.id}/campos-customizados", headers=headers_membro)
    assert res_list.status_code == 200
    assert len(res_list.json()["data"]) == 1

    # 3. Update member's own custom field value
    res_val = client.put(
        f"/api/organizacoes/{org1.id}/usuarios/{membro.id}/campos-customizados",
        headers=headers_membro,
        json={"campos_customizados": {"redmine_user_id": "77"}},
    )
    assert res_val.status_code == 200
    assert res_val.json()["data"]["redmine_user_id"] == "77"

    # 4. Get member's custom field value
    res_get_val = client.get(
        f"/api/organizacoes/{org1.id}/usuarios/{membro.id}/campos-customizados",
        headers=headers_membro,
    )
    assert res_get_val.status_code == 200
    assert res_get_val.json()["data"]["redmine_user_id"] == "77"

    # 5. Check Unit custom fields
    unidade = Unidade(nome="Departamento de Informática", sigla="DINF", id_organizacao=org1.id, inativo=False, ativo=True)
    db.add(unidade)
    db.commit()

    res_unit_val = client.put(
        f"/api/unidades/{unidade.id}/campos-customizados",
        headers=headers_gestor,
        json={"campos_customizados": {"redmine_project_id": "sistemas"}},
    )
    assert res_unit_val.status_code == 200
    assert res_unit_val.json()["data"]["redmine_project_id"] == "sistemas"

    res_get_unit_val = client.get(
        f"/api/unidades/{unidade.id}/campos-customizados",
        headers=headers_gestor,
    )
    assert res_get_unit_val.status_code == 200
    assert res_get_unit_val.json()["data"]["redmine_project_id"] == "sistemas"

    # 6. Multi-tenancy check: Org 2 manager cannot see or access Org 1 custom fields
    headers_org2 = {"Authorization": f"Bearer {token_gestor}", "X-Organization-Id": str(org2.id)}
    res_org2 = client.get(f"/api/organizacoes/{org2.id}/campos-customizados", headers=headers_org2)
    assert res_org2.status_code in (403, 404)  # Gestor has no link to Org 2

    db.close()


@pytest.mark.asyncio
async def test_live_tasks_endpoint_with_custom_fields_injection():
    db = TestingSessionLocal()

    org = Organizacao(nome="Universidade", sigla="UFPI", inativo=False, ativo=True)
    db.add(org)
    db.commit()

    user = Usuario(nome="Matheus Dev", usuario="matheus", email="matheus@ufpi.br", cpf="123.456.789-00", senha="hash", inativo=False, ativo=True, is_autorizado=True)
    db.add(user)
    db.commit()

    vinculo = UsuarioOrganizacao(
        id_usuario=user.id,
        id_organizacao=org.id,
        papel_organizacao=PapelOrganizacaoEnum.MEMBRO,
        campos_customizados={"redmine_user_id": "77"},
        inativo=False,
        ativo=True,
    )
    db.add(vinculo)
    db.commit()

    # Create task integration
    cfg = IntegracaoConfig(
        id_organizacao=org.id,
        nome="Redmine UFPI",
        provedor=ProvedorIntegracaoEnum.REDMINE,
        url_base="https://redmine.ufpi.br",
        tipo_autenticacao=TipoAutenticacaoEnum.API_KEY_QUERY,
        auth_static_config={"api_key": "secret123", "param_name": "key"},
        inativo=False,
        ativo=True,
    )
    db.add(cfg)
    db.commit()

    endpoint = IntegracaoEndpoint(
        id_integracao_config=cfg.id,
        nome="Receber Minhas Tarefas",
        path="/issues.json",
        metodo_http=MetodoHttpEnum.GET,
        tipo_integracao=TipoIntegracaoEnum.RECEBER_TAREFAS,
        modo_execucao=ModoExecucaoEnum.AUTOMATICO,
        parametros_config=[
            {
                "nome_parametro": "assigned_to_id",
                "tipo_localizacao": "QUERY",
                "tipo_origem": "DINAMICO_USUARIO",
                "valor_template": "{usuario_redmine_user_id}",
                "obrigatorio": True,
            }
        ],
        inativo=False,
        ativo=True,
    )
    db.add(endpoint)
    db.commit()

    mapeamento = IntegracaoMapeamento(
        id_integracao_endpoint=endpoint.id,
        items_root_path="issues",
        external_id_mode="SIMPLE",
        campo_codigo="id",
        campo_titulo="subject",
        campo_descricao="description",
        campo_status="status.name",
        campo_projeto="project.name",
        campo_tipo_anotacao="tracker.name",
        campo_prioridade="priority.name",
        campo_progresso="done_ratio",
        inativo=False,
        ativo=True,
    )
    db.add(mapeamento)
    db.commit()

    token = create_token_for_user(str(user.id))
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": str(org.id)}

    mock_redmine_response = {
        "issues": [
            {
                "id": 12345,
                "subject": "Implementar autenticação Redmine",
                "description": "Adicionar suporte a query param",
                "status": {"id": 2, "name": "Em Andamento"},
                "project": {"id": 10, "name": "Goal Getter"},
                "tracker": {"id": 1, "name": "Feature"},
                "priority": {"id": 4, "name": "Alta"},
                "done_ratio": 80,
            }
        ]
    }

    with patch("app.services.integration_engine_service.execute_integrated_request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = (200, 120.0, mock_redmine_response, {}, None, "https://redmine.ufpi.br/issues.json")

        res = client.get("/api/integracoes/tarefas-live", headers=headers)
        assert res.status_code == 200, res.text
        data = res.json()["data"]
        assert data["success"] is True
        assert data["total_tarefas"] == 1
        assert data["endpoint_ativo_nome"] == "Receber Minhas Tarefas"
        assert len(data["endpoints_disponiveis"]) >= 1
        assert data["endpoints_disponiveis"][0]["nome"] == "Receber Minhas Tarefas"
        tarefa = data["tarefas"][0]
        assert str(tarefa["id"]) == "12345"
        assert tarefa["titulo"] == "Implementar autenticação Redmine"
        assert tarefa["projeto"] == "Goal Getter"
        assert tarefa["tracker"] == "Feature"
        assert tarefa["prioridade"] == "Alta"
        assert tarefa["percentual_feito"] == 80
        assert tarefa["url_externa"] == "https://redmine.ufpi.br/issues/12345"

        # Verify that context had {usuario_redmine_user_id: '77'}
        called_kwargs = mock_req.call_args.kwargs
        assert called_kwargs["context"]["usuario_redmine_user_id"] == "77"

    db.close()


def test_resolve_item_url_template_parameterized():
    from app.services.schema_inspector_service import resolve_item_url_template

    item = {
        "id": 999,
        "project": {"id": 42, "name": "Core"},
        "tracker": {"name": "Bug"},
        "html_url": "https://direct-link.com/issue/999",
    }

    # 1. Direct path
    assert resolve_item_url_template("html_url", item) == "https://direct-link.com/issue/999"

    # 2. Parameterized URL template
    tpl = "https://redminedes.ufpi.br/{project.id}/{id}/view"
    assert resolve_item_url_template(tpl, item) == "https://redminedes.ufpi.br/42/999/view"

    # 3. Parameterized URL with project name and tracker
    tpl2 = "https://tracker.ufpi.br/{project.name}/{tracker.name}/{id}"
    assert resolve_item_url_template(tpl2, item) == "https://tracker.ufpi.br/Core/Bug/999"

    # 4. Empty or missing
    assert resolve_item_url_template(None, item) is None
    assert resolve_item_url_template("", item) is None

