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
    assert preview_res.preview_items[0].titulo == "Implementar Módulo de Segurança"
    assert preview_res.preview_items[0].status == "EM_ANDAMENTO"
    assert preview_res.preview_items[0].unidade_nome_mapeado == "Coordenação de Sistemas"


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

    # 3. Test POST /api/integracoes/{id}/endpoints
    ep_payload = {
        "nome": "Endpoint de Tarefas",
        "tipo_integracao": "RECEBER_TAREFAS",
        "path": "/tasks",
        "metodo_http": "GET",
        "modo_execucao": "GLOBAL_UNICO"
    }
    resp_ep = client.post(f"/api/integracoes/{created_id}/endpoints", json=ep_payload, headers=headers)
    assert resp_ep.status_code == 200
    ep_id = resp_ep.json()["data"]["id"]

    # 4. Test GET /api/integracoes/{id}/endpoints
    resp_eps = client.get(f"/api/integracoes/{created_id}/endpoints", headers=headers)
    assert resp_eps.status_code == 200
    assert len(resp_eps.json()["data"]) == 1

    # Clean overrides
    app.dependency_overrides.clear()
