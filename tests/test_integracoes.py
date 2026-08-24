import pytest
from datetime import date
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
from app.models.enums import (
    PapelOrganizacaoEnum,
    TipoIntegracaoEnum,
    ProvedorIntegracaoEnum,
    MetodoHttpEnum,
    TipoAutenticacaoEnum,
    ModoExecucaoEnum,
    ParametroLocalizacaoEnum,
    ParametroTipoOrigemEnum,
    StatusExecucaoEnum,
    OrigemDisparoEnum,
    EntregaStatusEnum,
    MetaStatusEnum,
)
from app.models.usuario import Usuario
from app.models.organizacao import Organizacao
from app.models.usuario_organizacao import UsuarioOrganizacao
from app.models.unidade import Unidade
from app.models.meta import Meta
from app.models.entrega import Entrega
from app.models.integracao_config import IntegracaoConfig
from app.models.integracao_endpoint import IntegracaoEndpoint
from app.models.integracao_mapeamento import IntegracaoMapeamento
from app.schemas.integracao import (
    IntegracaoConfigCreate,
    IntegracaoConfigUpdate,
    IntegracaoEndpointCreate,
    IntegracaoEndpointUpdate,
    IntegracaoMapeamentoCreate,
    IntegracaoMapeamentoBase,
    ParametroConfigSchema,
    DeParaUnidadeItem,
    DeParaUsuarioItem,
    TipoDeParaEnum,
    DeParaItemValor,
    DeParaRegra,
    TestConnectionRequest,
    InspectSchemaRequest,
    PreviewMappingRequest,
)
from app.services import integracao_service, schema_inspector_service, integration_engine_service

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
        usuario="gestor_integracoes",
        senha="hashed_pass",
        nome="Gestor Integrações",
        email="gestor.integracoes@ufpi.br",
        cpf="123.456.789-00",
        is_admin=False,
        is_autorizado=True,
        ativo=True,
        inativo=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    org = Organizacao(
        nome="Org Integrações Teste",
        sigla="ORG-INT",
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
        nome="Coordenação de Sistemas",
        sigla="CSIS",
        id_organizacao=org.id,
        ativo=True,
        inativo=False
    )
    db.add(unidade)

    meta = Meta(
        id_organizacao=org.id,
        id_unidade=unidade.id,
        titulo="Meta Padrão Integração",
        status=MetaStatusEnum.EM_ANDAMENTO,
        tipo_origem="INTERNA",
        valor_meta_inicial=0.0,
        valor_meta_pretendida=100.0,
        valor_meta_atual=0.0,
    )
    db.add(meta)
    db.commit()
    db.refresh(unidade)
    db.refresh(meta)

    return {"user": user, "org": org, "unidade": unidade, "meta": meta}


def test_integracao_config_and_endpoints_crud(db, setup_org_and_user):
    org = setup_org_and_user["org"]
    unidade = setup_org_and_user["unidade"]
    meta = setup_org_and_user["meta"]

    # 1. Create IntegracaoConfig with endpoints
    data = IntegracaoConfigCreate(
        nome="API Institucional UFPI",
        descricao="API central de dados e metas",
        provedor=ProvedorIntegracaoEnum.PETRVS,
        url_base="https://api.ufpi.br/v1",
        tipo_autenticacao=TipoAutenticacaoEnum.BEARER_TOKEN,
        auth_static_config={"token": "sample-secret-token"},
        ativo_sincronizacao=True,
        frequencia_cron="0 */2 * * *",
        endpoints=[
            IntegracaoEndpointCreate(
                nome="Receber Entregas do CSIS",
                tipo_integracao=TipoIntegracaoEnum.RECEBER_ENTREGAS,
                path="/unidades/{codigo_unidade}/entregas",
                metodo_http=MetodoHttpEnum.GET,
                modo_execucao=ModoExecucaoEnum.POR_UNIDADE,
                parametros_config=[
                    ParametroConfigSchema(
                        nome="codigo_unidade",
                        localizacao=ParametroLocalizacaoEnum.PATH,
                        tipo_origem=ParametroTipoOrigemEnum.DINAMICO_UNIDADE,
                        valor_template="{codigo_unidade}",
                        obrigatorio=True
                    )
                ],
                mapeamento=IntegracaoMapeamentoCreate(
                    items_root_path="data.entregas",
                    external_id_mode="COMPOSITE",
                    external_id_composite_paths=["plano_id", "codigo"],
                    external_id_composite_template="{plano_id}#{codigo}",
                    campo_titulo="descricao_atividade",
                    campo_descricao="detalhes",
                    campo_data_inicio="periodo.inicio",
                    campo_data_fim="periodo.prazo",
                    campo_status="situacao",
                    map_status_values={"CONCLUIDO": "ENTREGUE", "EM_EXECUCAO": "EM_ANDAMENTO"},
                    campo_progresso="percentual_concluido",
                    campo_responsavel="cpf_servidor",
                    campo_unidade_origem="unidade_sigla",
                    map_unidades_values=[
                        DeParaUnidadeItem(codigo_externo="CSIS", id_unidade=unidade.id, nome_externo="Coordenação de Sistemas")
                    ],
                    default_id_meta=meta.id,
                    default_id_unidade=unidade.id
                )
            )
        ]
    )

    created = integracao_service.create_integracao(db, org.id, data)
    assert created.id is not None
    assert created.nome == "API Institucional UFPI"
    assert created.url_base == "https://api.ufpi.br/v1"
    assert len(created.endpoints) == 1
    assert created.endpoints[0].nome == "Receber Entregas do CSIS"
    assert created.endpoints[0].mapeamento is not None
    assert created.endpoints[0].mapeamento.external_id_mode == "COMPOSITE"

    # 2. Update config
    update_data = IntegracaoConfigUpdate(nome="API Institucional UFPI Atualizada")
    updated = integracao_service.update_integracao(db, org.id, created.id, update_data)
    assert updated.nome == "API Institucional UFPI Atualizada"

    # 3. Add second endpoint (Receber Metas)
    ep2_data = IntegracaoEndpointCreate(
        nome="Receber Metas Globais",
        tipo_integracao=TipoIntegracaoEnum.RECEBER_METAS,
        path="/metas?ano={ano_atual}",
        metodo_http=MetodoHttpEnum.GET,
        modo_execucao=ModoExecucaoEnum.GLOBAL_UNICO,
        mapeamento=IntegracaoMapeamentoCreate(
            items_root_path="results",
            campo_titulo="nome_meta",
            campo_codigo="cod",
            campo_valor_inicial="v_ini",
            campo_valor_pretendido="v_pret",
            campo_valor_atual="v_atual",
            campo_status="status_meta",
            map_status_values={"FINALIZADA": "CONCLUIDA"}
        )
    )
    created_ep2 = integracao_service.create_endpoint(db, org.id, created.id, ep2_data)
    assert created_ep2.id is not None
    assert created_ep2.tipo_integracao == TipoIntegracaoEnum.RECEBER_METAS

    # 4. List endpoints
    endpoints_list = integracao_service.list_endpoints(db, org.id, created.id)
    assert len(endpoints_list) == 2

    # 5. List configs
    configs = integracao_service.list_integracoes(db, org.id)
    assert len(configs) == 1
    assert len(configs[0].endpoints) == 2

    # 6. Delete endpoint
    integracao_service.delete_endpoint(db, org.id, created_ep2.id)
    endpoints_after_del = integracao_service.list_endpoints(db, org.id, created.id)
    assert len(endpoints_after_del) == 1

    # 7. Delete config
    integracao_service.delete_integracao(db, org.id, created.id)
    configs_after_del = integracao_service.list_integracoes(db, org.id)
    assert len(configs_after_del) == 0


@pytest.mark.asyncio
async def test_schema_inspector_and_live_preview():
    sample_payload = {
        "status": "success",
        "data": {
            "plano_codigo": "PLAN-2026",
            "results": [
                {
                    "id": 101,
                    "codigo_entrega": "ENT-01",
                    "nome_tarefa": "Implementar Módulo de Segurança",
                    "detalhes": "OAuth2 e JWT",
                    "datas": {
                        "inicio": "2026-03-01",
                        "fim": "2026-06-30"
                    },
                    "estado": "EM_EXECUCAO",
                    "progresso": 75,
                    "servidor_cpf": "12345678900",
                    "unidade": "CSIS"
                }
            ]
        }
    }

    # 1. Inspect Schema using raw sample
    req_inspect = InspectSchemaRequest(
        url_base="https://api.fake.ufpi.br",
        path="/v1/items",
        raw_sample=sample_payload
    )
    inspected = await schema_inspector_service.inspect_schema(req_inspect)
    assert inspected.success is True
    assert "data.results" in inspected.detected_arrays
    assert "nome_tarefa" in inspected.discovered_fields

    # 2. Preview Mapping with Composite Key and Unit De-Para
    req_preview = PreviewMappingRequest(
        tipo_integracao=TipoIntegracaoEnum.RECEBER_ENTREGAS,
        raw_data=sample_payload,
        mapeamento=IntegracaoMapeamentoBase(
            items_root_path="data.results",
            external_id_mode="COMPOSITE",
            external_id_composite_paths=["id", "codigo_entrega"],
            external_id_composite_template="ITEM-{id}-{codigo_entrega}",
            campo_titulo="nome_tarefa",
            campo_descricao="detalhes",
            campo_data_inicio="datas.inicio",
            campo_data_fim="datas.fim",
            campo_status="estado",
            map_status_values={"CONCLUIDO": "ENTREGUE", "EM_EXECUCAO": "EM_ANDAMENTO"},
            campo_progresso="progresso",
            campo_responsavel="servidor_cpf",
            campo_unidade_origem="unidade",
            map_unidades_values=[
                DeParaUnidadeItem(codigo_externo="CSIS", id_unidade=uuid4(), nome_externo="Coordenação de Sistemas")
            ]
        )
    )
    preview_res = await schema_inspector_service.preview_mapping(req_preview)
    assert preview_res.success is True
    assert preview_res.total_raw_items == 1
    assert preview_res.preview_items[0].external_id == "ITEM-101-ENT-01"
    assert preview_res.preview_items[0].unidade_nome_mapeado == "Coordenação de Sistemas"


@pytest.mark.asyncio
async def test_preview_mapping_with_unified_regras_de_para():
    sample_payload = {
        "entregas": [
            {
                "id": "ENT-99",
                "titulo": "Novo Portal UFPI",
                "situacao": "OPEN",
                "codigo_unidade": "STI_DES",
                "responsavel_id": "usr_77",
            }
        ]
    }
    req_preview = PreviewMappingRequest(
        tipo_integracao=TipoIntegracaoEnum.RECEBER_ENTREGAS,
        raw_data=sample_payload,
        mapeamento=IntegracaoMapeamentoBase(
            items_root_path="entregas",
            campo_titulo="titulo",
            campo_status="situacao",
            campo_unidade_origem="codigo_unidade",
            campo_responsavel="responsavel_id",
            regras_de_para=[
                DeParaRegra(
                    tipo=TipoDeParaEnum.STATUS,
                    campo_alvo="campo_status",
                    nome_regra="Mapeamento de Status",
                    valores=[
                        DeParaItemValor(de="OPEN", para="EM_ANDAMENTO", rotulo_externo="Em Andamento"),
                        DeParaItemValor(de="DONE", para="ENTREGUE", rotulo_externo="Entregue")
                    ]
                ),
                DeParaRegra(
                    tipo=TipoDeParaEnum.UNIDADE,
                    campo_alvo="campo_unidade_origem",
                    nome_regra="Mapeamento de Unidades",
                    valores=[
                        DeParaItemValor(de="STI_DES", para=str(uuid4()), rotulo_externo="Superintendência de TI")
                    ]
                ),
                DeParaRegra(
                    tipo=TipoDeParaEnum.USUARIO,
                    campo_alvo="campo_responsavel",
                    nome_regra="Mapeamento de Responsáveis",
                    valores=[
                        DeParaItemValor(de="usr_77", para=str(uuid4()), rotulo_externo="Matheus Silva")
                    ]
                )
            ]
        )
    )
    res = await schema_inspector_service.preview_mapping(req_preview)
    assert res.success is True
    assert len(res.preview_items) == 1
    item = res.preview_items[0]
    assert item.status == "EM_ANDAMENTO"
    assert item.unidade_nome_mapeado == "Superintendência de TI"
    assert item.responsavel_identificador == "Matheus Silva"


@pytest.mark.asyncio
async def test_integration_engine_sync_metas_and_entregas(db, setup_org_and_user):
    org = setup_org_and_user["org"]
    unidade = setup_org_and_user["unidade"]
    user = setup_org_and_user["user"]

    # Create Connection
    cfg_data = IntegracaoConfigCreate(
        nome="Petrvs Completo",
        provedor=ProvedorIntegracaoEnum.PETRVS,
        url_base="https://petrvs.ufpi.br/api",
        tipo_autenticacao=TipoAutenticacaoEnum.NONE,
        endpoints=[
            IntegracaoEndpointCreate(
                nome="Metas Institucionais",
                tipo_integracao=TipoIntegracaoEnum.RECEBER_METAS,
                path="/metas",
                modo_execucao=ModoExecucaoEnum.GLOBAL_UNICO,
                mapeamento=IntegracaoMapeamentoCreate(
                    items_root_path="metas",
                    campo_titulo="titulo",
                    campo_codigo="cod",
                    campo_valor_inicial="v_ini",
                    campo_valor_pretendido="v_pret",
                    campo_valor_atual="v_atual",
                    campo_status="situacao",
                    map_status_values={"ATIVA": "EM_ANDAMENTO", "CONCLUIDA": "CONCLUIDA"}
                )
            ),
            IntegracaoEndpointCreate(
                nome="Entregas da Unidade",
                tipo_integracao=TipoIntegracaoEnum.RECEBER_ENTREGAS,
                path="/entregas?unidade={codigo_unidade}",
                modo_execucao=ModoExecucaoEnum.POR_UNIDADE,
                parametros_config=[
                    ParametroConfigSchema(
                        nome="codigo_unidade",
                        localizacao=ParametroLocalizacaoEnum.QUERY,
                        tipo_origem=ParametroTipoOrigemEnum.DINAMICO_UNIDADE,
                        valor_template="{codigo_unidade}",
                        obrigatorio=True
                    )
                ],
                mapeamento=IntegracaoMapeamentoCreate(
                    items_root_path="entregas",
                    campo_titulo="nome",
                    campo_status="status",
                    campo_progresso="pct",
                    campo_responsavel="cpf",
                    map_unidades_values=[
                        DeParaUnidadeItem(codigo_externo="CSIS", id_unidade=unidade.id, nome_externo="CSIS")
                    ],
                    map_usuarios_values=[
                        DeParaUsuarioItem(identificador_externo="12345678900", id_usuario=user.id, nome_externo="Gestor")
                    ]
                )
            )
        ]
    )

    created_cfg = integracao_service.create_integracao(db, org.id, cfg_data)
    ep_metas = [ep for ep in created_cfg.endpoints if ep.tipo_integracao == TipoIntegracaoEnum.RECEBER_METAS][0]
    ep_entregas = [ep for ep in created_cfg.endpoints if ep.tipo_integracao == TipoIntegracaoEnum.RECEBER_ENTREGAS][0]

    # Mock HTTP responses
    metas_payload = {
        "metas": [
            {
                "id": "META-100",
                "titulo": "Digitalizar 100% dos Processos",
                "cod": "MET-DIGITAL",
                "v_ini": 0,
                "v_pret": 100,
                "v_atual": 45,
                "situacao": "ATIVA"
            }
        ]
    }

    entregas_payload = {
        "entregas": [
            {
                "id": "ENT-200",
                "nome": "Migração de Servidores",
                "status": "EM_ANDAMENTO",
                "pct": 80,
                "cpf": "12345678900"
            }
        ]
    }

    async def mock_execute(*args, **kwargs):
        path = kwargs.get("path") or ""
        if "metas" in path:
            return 200, 10.0, metas_payload, {}, None
        else:
            return 200, 10.0, entregas_payload, {}, None

    with patch("app.services.integration_engine_service.execute_integrated_request", side_effect=mock_execute):
        # 1. Sync Metas Endpoint
        hist_metas = await integration_engine_service.run_endpoint_sync(
            db=db,
            endpoint_id=ep_metas.id,
            disparo=OrigemDisparoEnum.MANUAL,
            id_usuario_executor=user.id
        )
        assert hist_metas.status == StatusExecucaoEnum.SUCESSO
        assert hist_metas.total_criados == 1

        created_meta = db.query(Meta).filter(Meta.external_id == "META-100").first()
        assert created_meta is not None
        assert created_meta.titulo == "Digitalizar 100% dos Processos"
        assert created_meta.status == MetaStatusEnum.EM_ANDAMENTO

        # 2. Sync Entregas Endpoint
        hist_entregas = await integration_engine_service.run_endpoint_sync(
            db=db,
            endpoint_id=ep_entregas.id,
            disparo=OrigemDisparoEnum.MANUAL,
            id_usuario_executor=user.id
        )
        assert hist_entregas.status == StatusExecucaoEnum.SUCESSO
        assert hist_entregas.total_criados == 1

        created_entrega = db.query(Entrega).filter(Entrega.external_id == "ENT-200").first()
        assert created_entrega is not None
        assert created_entrega.titulo == "Migração de Servidores"
        assert created_entrega.id_usuario_responsavel == user.id
        assert created_entrega.id_unidade == unidade.id


def test_api_routes_with_test_client(db, setup_org_and_user):
    user = setup_org_and_user["user"]
    org = setup_org_and_user["org"]

    token = jwt.encode(
        {"sub": str(user.id), "role": "GESTOR"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-Id": str(org.id)
    }

    # 1. Test POST /api/integracoes/
    payload = {
        "nome": "Integração REST Externa",
        "provedor": "CUSTOM_REST",
        "url_base": "https://api.exemplo.com",
        "tipo_autenticacao": "NONE"
    }
    resp = client.post("/api/integracoes/", json=payload, headers=headers)
    assert resp.status_code == 200
    created_id = resp.json()["data"]["id"]

    # 2. Test GET /api/integracoes/
    resp_list = client.get("/api/integracoes/", headers=headers)
    assert resp_list.status_code == 200
    assert len(resp_list.json()["data"]) == 1

    # 3. Test POST /api/integracoes/{id}/endpoints with full task fields mapping
    ep_payload = {
        "nome": "Endpoint de Tarefas",
        "tipo_integracao": "RECEBER_TAREFAS",
        "path": "/tasks",
        "metodo_http": "GET",
        "modo_execucao": "GLOBAL_UNICO",
        "mapeamento": {
            "items_root_path": "issues",
            "campo_titulo": "subject",
            "campo_projeto": "project.name",
            "campo_prioridade": "priority.name",
            "campo_autor": "author.name",
            "campo_data_atualizacao": "updated_on",
            "campo_link_externo": "https://redminedes.ufpi.br/{project.id}/{id}/view",
            "campos_extras": [{"chave": "custom_obs", "caminho": "custom_fields.0.value"}]
        }
    }
    resp_ep = client.post(f"/api/integracoes/{created_id}/endpoints", json=ep_payload, headers=headers)
    assert resp_ep.status_code == 200
    ep_data = resp_ep.json()["data"]
    assert ep_data["mapeamento"]["campo_projeto"] == "project.name"
    assert ep_data["mapeamento"]["campo_prioridade"] == "priority.name"
    assert ep_data["mapeamento"]["campo_autor"] == "author.name"
    assert ep_data["mapeamento"]["campo_data_atualizacao"] == "updated_on"
    assert ep_data["mapeamento"]["campo_link_externo"] == "https://redminedes.ufpi.br/{project.id}/{id}/view"
    assert len(ep_data["mapeamento"]["campos_extras"]) == 1

    # 4. Test PUT /api/integracoes/{id} to save as RASCUNHO with updated endpoints and campo_link_externo
    update_payload = {
        "status": "RASCUNHO",
        "nome": "Integração Rascunho",
        "endpoints": [
            {
                "nome": "Endpoint Tarefas Atualizado",
                "tipo_integracao": "RECEBER_TAREFAS",
                "path": "/tasks_updated",
                "metodo_http": "GET",
                "modo_execucao": "GLOBAL_UNICO",
                "mapeamento": {
                    "items_root_path": "issues",
                    "campo_titulo": "subject",
                    "campo_projeto": "project.name",
                    "campo_prioridade": "priority.name",
                    "campo_link_externo": "https://redmine.ufpi.br/issues/{id}",
                }
            }
        ]
    }
    resp_update = client.put(f"/api/integracoes/{created_id}", json=update_payload, headers=headers)
    assert resp_update.status_code == 200
    updated_data = resp_update.json()["data"]
    assert updated_data["status"] == "RASCUNHO"
    assert updated_data["nome"] == "Integração Rascunho"
    assert len(updated_data["endpoints"]) == 1
    assert updated_data["endpoints"][0]["mapeamento"]["campo_link_externo"] == "https://redmine.ufpi.br/issues/{id}"

    # 5. Test GET /api/integracoes/{id}/endpoints
    resp_eps = client.get(f"/api/integracoes/{created_id}/endpoints", headers=headers)
    assert resp_eps.status_code == 200
    assert len(resp_eps.json()["data"]) == 1
    ep_tasks_id = resp_eps.json()["data"][0]["id"]
    assert resp_eps.json()["data"][0]["mapeamento"]["campo_link_externo"] == "https://redmine.ufpi.br/issues/{id}"

    # 6. Test preview_endpoint_sync for RECEBER_TAREFAS
    tasks_api_payload = {
        "issues": [
            {
                "id": 999,
                "subject": "Corrigir bug no login",
                "project": {"id": 1, "name": "Sistema Acadêmico"},
                "priority": {"id": 2, "name": "Alta"},
                "author": {"id": 5, "name": "Admin"},
                "tracker": {"name": "TODAY"},
                "status": {"name": "Em Andamento"}
            }
        ]
    }
    with patch("app.services.integration_engine_service.execute_integrated_request", return_value=(200, 15.0, tasks_api_payload, {}, None)):
        resp_preview = client.post(
            f"/api/integracoes/{created_id}/endpoints/{ep_tasks_id}/preview-sync",
            json={},
            headers=headers
        )
        assert resp_preview.status_code == 200
        preview_data = resp_preview.json()["data"]
        assert preview_data["total_encontrados"] == 1
        assert len(preview_data["items"]) == 1
        item0 = preview_data["items"][0]
        assert item0["external_id"] == "999"
        assert item0["titulo"] == "Corrigir bug no login"
        assert item0["projeto"] == "Sistema Acadêmico"
        assert item0["prioridade"] == "Alta"
        assert item0["link_externo"] == "https://redmine.ufpi.br/issues/999"

    # Clean overrides
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_integracao_redmine_api_key_query(db, setup_org_and_user):
    """Tests Redmine-style API key via query param in connection test & request execution."""
    org = setup_org_and_user["org"]

    # 1. Test execute_integrated_request query parameter injection
    req_url = "https://redmine.ufpi.br"
    tipo_auth = TipoAutenticacaoEnum.API_KEY_QUERY
    auth_config = {"param_name": "key", "api_key": "redmine_secret_key_123"}
    params_custom = [
        ParametroConfigSchema(
            nome="project_id",
            localizacao=ParametroLocalizacaoEnum.QUERY,
            tipo_origem=ParametroTipoOrigemEnum.FIXO,
            valor_template="sistemas_ufpi",
        )
    ]

    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = lambda: {"issues": [{"id": 1, "subject": "Tarefa Redmine"}]}
        mock_get.return_value = mock_response

        status_code, latency, data, resp_headers, token = await schema_inspector_service.execute_integrated_request(
            url_base=req_url,
            path="issues.json",
            metodo_http=MetodoHttpEnum.GET,
            tipo_autenticacao=tipo_auth,
            auth_static_config=auth_config,
            parametros_config=params_custom,
        )

        assert status_code == 200
        assert token == "redmine_secret_key_123"
        assert "issues" in data
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args.kwargs
        assert call_kwargs["params"]["key"] == "redmine_secret_key_123"
        assert call_kwargs["params"]["project_id"] == "sistemas_ufpi"


@pytest.mark.asyncio
async def test_integration_selective_sync_entregas(db, setup_org_and_user):
    """Tests that when selected_external_ids is provided, only selected deliveries are saved into the organization."""
    org = setup_org_and_user["org"]
    user = setup_org_and_user["user"]
    unidade = setup_org_and_user["unidade"]

    # Create integration config
    cfg_create = IntegracaoConfigCreate(
        nome="Integração Entregas Seletivas",
        provedor=ProvedorIntegracaoEnum.CUSTOM_REST,
        url_base="https://api.petrvs.ufpi.br",
        tipo_autenticacao=TipoAutenticacaoEnum.NONE,
        endpoints=[
            IntegracaoEndpointCreate(
                nome="Entregas Múltiplas",
                tipo_integracao=TipoIntegracaoEnum.RECEBER_ENTREGAS,
                path="/entregas",
                metodo_http=MetodoHttpEnum.GET,
                mapeamento=IntegracaoMapeamentoCreate(
                    items_root_path="entregas",
                    campo_titulo="nome",
                    campo_status="status",
                    campo_progresso="pct",
                    campo_responsavel="cpf",
                    default_id_unidade=unidade.id,
                )
            )
        ]
    )

    created_cfg = integracao_service.create_integracao(db=db, id_organizacao=org.id, data=cfg_create)
    ep = created_cfg.endpoints[0]

    api_payload = {
        "entregas": [
            {"id": "ENT-1", "nome": "Entrega 1", "status": "EM_ANDAMENTO", "pct": 50, "cpf": user.cpf},
            {"id": "ENT-2", "nome": "Entrega 2", "status": "ENTREGUE", "pct": 100, "cpf": user.cpf},
            {"id": "ENT-3", "nome": "Entrega 3", "status": "NAO_INICIADA", "pct": 0, "cpf": user.cpf},
        ]
    }

    with patch("app.services.integration_engine_service.execute_integrated_request", return_value=(200, 10.0, api_payload, {}, None)):
        # 1. Sync only ENT-1 and ENT-3 (selective manual sync)
        hist = await integration_engine_service.run_endpoint_sync(
            db=db,
            endpoint_id=ep.id,
            disparo=OrigemDisparoEnum.MANUAL,
            id_usuario_executor=user.id,
            selected_external_ids=["ENT-1", "ENT-3"]
        )

        assert hist.status == StatusExecucaoEnum.SUCESSO
        assert hist.total_criados == 2

        e1 = db.query(Entrega).filter(Entrega.id_organizacao == org.id, Entrega.external_id == "ENT-1").first()
        assert e1 is not None
        assert e1.titulo == "Entrega 1"
        assert e1.id_usuario_responsavel == user.id

        e2 = db.query(Entrega).filter(Entrega.id_organizacao == org.id, Entrega.external_id == "ENT-2").first()
        assert e2 is None  # Not selected, should NOT be saved!

        e3 = db.query(Entrega).filter(Entrega.id_organizacao == org.id, Entrega.external_id == "ENT-3").first()
        assert e3 is not None
        assert e3.titulo == "Entrega 3"

        # 2. Full sync without selection (e.g. Scheduled CRON) saves all, creating ENT-2 and keeping ENT-1, ENT-3 unchanged
        hist_cron = await integration_engine_service.run_endpoint_sync(
            db=db,
            endpoint_id=ep.id,
            disparo=OrigemDisparoEnum.CRON_AGENDAMENTO,
            id_usuario_executor=None,
            selected_external_ids=None
        )

        assert hist_cron.status == StatusExecucaoEnum.SUCESSO
        assert hist_cron.total_criados == 1  # ENT-2 was created
        assert hist_cron.total_inalterados == 2  # ENT-1 and ENT-3 already existed and are unchanged

        e2_after = db.query(Entrega).filter(Entrega.id_organizacao == org.id, Entrega.external_id == "ENT-2").first()
        assert e2_after is not None
        assert e2_after.titulo == "Entrega 2"


@pytest.mark.asyncio
async def test_inspect_schema_with_iteration_contexts():
    """Tests that inspect_schema iterates through iteration_contexts and resolves placeholders like {usuario_cpf}."""
    req = InspectSchemaRequest(
        url_base="https://api.petrvs.ufpi.br",
        path="/entregas?cpf={usuario_cpf}",
        metodo_http=MetodoHttpEnum.GET,
        tipo_autenticacao=TipoAutenticacaoEnum.NONE,
        iteration_contexts=[
            {"id_usuario": "u1", "usuario_cpf": "11122233344"},
            {"id_usuario": "u2", "usuario_cpf": "55566677788"},
        ],
    )

    requested_urls = []

    async def mock_execute(**kwargs):
        ctx = kwargs.get("context") or {}
        cpf = ctx.get("usuario_cpf", "")
        requested_urls.append(f"https://api.petrvs.ufpi.br/entregas?cpf={cpf}")
        return (
            200,
            12.0,
            {"entregas": [{"id": f"ENT-{cpf}", "titulo": f"Entrega do CPF {cpf}", "status": "OK"}]},
            {},
            None,
        )

    with patch("app.services.schema_inspector_service.execute_integrated_request", side_effect=mock_execute):
        res = await schema_inspector_service.inspect_schema(req)

        assert res.success is True
        assert len(requested_urls) == 2
        assert "cpf=11122233344" in requested_urls[0]
        assert "cpf=55566677788" in requested_urls[1]
        assert "entregas" in res.detected_arrays
        assert "titulo" in res.discovered_fields
        assert "id" in res.discovered_fields
        assert "status" in res.discovered_fields


@pytest.mark.asyncio
async def test_preview_integration_sync_dry_run_new_items(db, setup_org_and_user):
    """Tests dry-run preview simulation for newly incoming items where acao='CRIAR'."""
    org = setup_org_and_user["org"]
    user = setup_org_and_user["user"]

    integracao = IntegracaoConfig(
        id_organizacao=org.id,
        nome="Integracao Petrvs Preview",
        url_base="https://api.petrvs.ufpi.br",
        tipo_autenticacao=TipoAutenticacaoEnum.NONE,
        ativo=True,
    )
    db.add(integracao)
    db.commit()
    db.refresh(integracao)

    ep = IntegracaoEndpoint(
        id_integracao_config=integracao.id,
        nome="Entregas por Usuário",
        path="/transparencia-api/entregas?cpf={usuario_cpf}",
        metodo_http=MetodoHttpEnum.GET,
        tipo_integracao=TipoIntegracaoEnum.RECEBER_ENTREGAS,
        modo_execucao=ModoExecucaoEnum.MANUAL_PAINEL,
        escopo_usuarios="TODOS",
        escopo_unidades="TODAS",
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)

    map_cfg = IntegracaoMapeamento(
        id_integracao_endpoint=ep.id,
        items_root_path="entregas",
        external_id_mode="SIMPLE",
        external_id_path="id",
        campo_titulo="titulo",
        campo_status="status",
    )
    db.add(map_cfg)
    db.commit()

    async def mock_execute(**kwargs):
        return (
            200,
            15.0,
            {"entregas": [{"id": "NEW-ENT-99", "titulo": "Nova Entrega Simulação", "status": "HOMOLOGADO"}]},
            {},
            None,
        )

    with patch("app.services.integration_engine_service.execute_integrated_request", side_effect=mock_execute):
        res = await integration_engine_service.preview_endpoint_sync(
            db=db,
            endpoint_id=ep.id,
            current_user=user,
        )

        assert res.total_novos == 1
        assert len(res.items) == 1
        assert res.items[0].external_id == "NEW-ENT-99"
        assert res.items[0].acao == "CRIAR"
        assert res.items[0].titulo == "Nova Entrega Simulação"


@pytest.mark.asyncio
async def test_preview_sync_deduplicates_external_ids(db, setup_org_and_user):
    """Tests that preview endpoint sync deduplicates multiple items with same external_id and tracks occurrence count."""
    org = setup_org_and_user["org"]
    user = setup_org_and_user["user"]

    integracao = IntegracaoConfig(
        id_organizacao=org.id,
        nome="Integracao Petrvs Dup Test",
        url_base="https://api.petrvs.ufpi.br",
        tipo_autenticacao=TipoAutenticacaoEnum.NONE,
        ativo=True,
    )
    db.add(integracao)
    db.commit()

    ep = IntegracaoEndpoint(
        id_integracao_config=integracao.id,
        nome="Entregas Múltiplas",
        path="/transparencia-api/entregas",
        metodo_http=MetodoHttpEnum.GET,
        tipo_integracao=TipoIntegracaoEnum.RECEBER_ENTREGAS,
        modo_execucao=ModoExecucaoEnum.MANUAL_PAINEL,
        escopo_usuarios="TODOS",
        escopo_unidades="TODAS",
    )
    db.add(ep)
    db.commit()

    map_cfg = IntegracaoMapeamento(
        id_integracao_endpoint=ep.id,
        items_root_path="entregas",
        external_id_mode="SIMPLE",
        external_id_path="id",
        campo_titulo="titulo",
        campo_status="status",
    )
    db.add(map_cfg)
    db.commit()

    api_payload = {
        "entregas": [
            {"id": "ENT-DUP", "titulo": "Entrega Duplicada 1", "status": "HOMOLOGADO"},
            {"id": "ENT-DUP", "titulo": "Entrega Duplicada 2", "status": "HOMOLOGADO"},
            {"id": "ENT-DUP", "titulo": "Entrega Duplicada 3", "status": "HOMOLOGADO"},
            {"id": "ENT-UNICA", "titulo": "Entrega Única", "status": "HOMOLOGADO"},
        ]
    }

    with patch("app.services.integration_engine_service.execute_integrated_request", return_value=(200, 10.0, api_payload, {}, None)):
        res = await integration_engine_service.preview_endpoint_sync(
            db=db,
            endpoint_id=ep.id,
            current_user=user,
        )

        assert res.total_encontrados == 4
        assert len(res.items) == 2

        dup_item = next((i for i in res.items if i.external_id == "ENT-DUP"), None)
        assert dup_item is not None
        assert dup_item.quantidade_registros == 3

        unique_item = next((i for i in res.items if i.external_id == "ENT-UNICA"), None)
        assert unique_item is not None
        assert unique_item.quantidade_registros == 1


@pytest.mark.asyncio
async def test_preview_mapping_deduplicates_composite_external_keys():
    """Tests that preview_mapping with COMPOSITE external key deduplicates items and calculates quantidade_registros."""
    from app.schemas.integracao import PreviewMappingRequest, IntegracaoMapeamentoCreate

    req = PreviewMappingRequest(
        tipo_integracao=TipoIntegracaoEnum.RECEBER_ENTREGAS,
        raw_data={
            "dados": [
                {"projeto_id": "PRJ-10", "modulo_cod": "A1", "nome": "Item Comp 1", "status": "FEITO"},
                {"projeto_id": "PRJ-10", "modulo_cod": "A1", "nome": "Item Comp 1 Repetido", "status": "FEITO"},
                {"projeto_id": "PRJ-20", "modulo_cod": "B2", "nome": "Item Comp 2", "status": "PENDENTE"},
            ]
        },
        mapeamento=IntegracaoMapeamentoCreate(
            items_root_path="dados",
            external_id_mode="COMPOSITE",
            external_id_composite_template="{projeto_id}:{modulo_cod}",
            external_id_composite_paths=["projeto_id", "modulo_cod"],
            campo_titulo="nome",
            campo_status="status",
        )
    )

    res = await schema_inspector_service.preview_mapping(req)

    assert res.success is True
    assert res.total_raw_items == 3
    assert len(res.preview_items) == 2

    dup = next((i for i in res.preview_items if i.external_id == "PRJ-10:A1"), None)
    assert dup is not None
    assert dup.quantidade_registros == 2

    single = next((i for i in res.preview_items if i.external_id == "PRJ-20:B2"), None)
    assert single is not None
    assert single.quantidade_registros == 1


@pytest.mark.asyncio
async def test_preview_sync_detects_existing_record_and_altered_fields(db, setup_org_and_user):
    """Tests that preview endpoint sync detects existing records in DB and identifies changed fields in blue."""
    from app.models.entrega import Entrega
    from app.models.enums import EntregaStatusEnum

    org = setup_org_and_user["org"]
    user = setup_org_and_user["user"]

    integracao = IntegracaoConfig(
        id_organizacao=org.id,
        nome="Integracao Diff Check",
        url_base="https://api.petrvs.ufpi.br",
        tipo_autenticacao=TipoAutenticacaoEnum.NONE,
        ativo=True,
    )
    db.add(integracao)
    db.commit()

    ep = IntegracaoEndpoint(
        id_integracao_config=integracao.id,
        nome="Entregas Diff Endpoint",
        path="/transparencia-api/entregas",
        metodo_http=MetodoHttpEnum.GET,
        tipo_integracao=TipoIntegracaoEnum.RECEBER_ENTREGAS,
        modo_execucao=ModoExecucaoEnum.MANUAL_PAINEL,
        escopo_usuarios="TODOS",
        escopo_unidades="TODAS",
    )
    db.add(ep)
    db.commit()

    map_cfg = IntegracaoMapeamento(
        id_integracao_endpoint=ep.id,
        items_root_path="entregas",
        external_id_mode="SIMPLE",
        external_id_path="id",
        campo_titulo="titulo",
        campo_status="status",
        campo_progresso="progresso",
    )
    db.add(map_cfg)
    db.commit()

    # Pre-existing entrega in database
    existing_entrega = Entrega(
        id_organizacao=org.id,
        id_integracao_config=integracao.id,
        external_id="ENT-EXISTENTE",
        titulo="Título Antigo no Banco",
        status=EntregaStatusEnum.EM_ANDAMENTO,
        progresso_percentual=50,
    )
    db.add(existing_entrega)
    db.commit()

    api_payload = {
        "entregas": [
            {
                "id": "ENT-EXISTENTE",
                "titulo": "Título Atualizado da API",
                "status": "EM_ANDAMENTO",
                "progresso": "85%",
            }
        ]
    }

    with patch("app.services.integration_engine_service.execute_integrated_request", return_value=(200, 10.0, api_payload, {}, None)):
        res = await integration_engine_service.preview_endpoint_sync(
            db=db,
            endpoint_id=ep.id,
            current_user=user,
        )

        assert res.total_atualizados == 1
        assert res.total_novos == 0
        assert len(res.items) == 1

        item = res.items[0]
        assert item.external_id == "ENT-EXISTENTE"
        assert item.ja_existe is True
        assert item.acao == "ATUALIZAR"
        assert "titulo" in item.campos_alterados
        assert "progresso_percentual" in item.campos_alterados
        assert "status" not in item.campos_alterados
        assert item.valores_anteriores["titulo"] == "Título Antigo no Banco"
        assert item.valores_anteriores["progresso_percentual"] == 50






