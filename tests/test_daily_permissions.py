import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.atribuicao import Atribuicao
from app.models.diario_config import DiarioConfig
from app.models.enums import NivelCodigoEnum, PapelOrganizacaoEnum, TipoNivelEnum
from app.models.grupo import GrupoTrabalho
from app.models.nivel import Nivel
from app.models.organizacao import Organizacao
from app.models.perfil import Perfil
from app.models.unidade import Unidade
from app.models.usuario import Usuario
from app.models.usuario_organizacao import UsuarioOrganizacao
from app.schemas.daily import DiarioConfigUpdate
from app.services import auth_service, daily_config_service, daily_permission_service

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


def create_user(db, username, email, is_admin=False):
    u = Usuario(
        usuario=username,
        nome=username.capitalize(),
        email=email,
        senha=auth_service.get_password_hash("password123"),
        is_admin=is_admin,
        is_autorizado=True,
        inativo=False,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_daily_permissions_matrix(db):
    # 1. Setup Níveis
    nivel_chefe_unidade = Nivel(valor=NivelCodigoEnum.CHEFE_UNIDADE.value, nome="Chefe de Unidade", tipo=TipoNivelEnum.PERFIL)
    nivel_gestor_grupo = Nivel(valor=NivelCodigoEnum.GESTOR_GRUPO.value, nome="Gestor de Grupo", tipo=TipoNivelEnum.ATRIBUICAO)
    nivel_participante = Nivel(valor=NivelCodigoEnum.PARTICIPANTE.value, nome="Participante", tipo=TipoNivelEnum.ATRIBUICAO)
    db.add_all([nivel_chefe_unidade, nivel_gestor_grupo, nivel_participante])
    db.commit()

    # 2. Setup Organização, Unidade e Grupo
    org = Organizacao(nome="Org Teste Daily", sigla="OTD")
    db.add(org)
    db.commit()

    unidade = Unidade(nome="Unidade Daily", sigla="UD", id_organizacao=org.id)
    db.add(unidade)
    db.commit()

    grupo = GrupoTrabalho(nome="Grupo Daily", id_unidade=unidade.id, id_organizacao=org.id)
    db.add(grupo)
    db.commit()

    config = DiarioConfig(id_grupo=grupo.id, periodo_addnota_inicio="08:00", periodo_addnota_fim="18:00")
    db.add(config)
    db.commit()

    # 3. Setup Usuários com diferentes papéis
    u_admin = create_user(db, "admin", "admin@ufpi.br", is_admin=True)
    u_org_gestor = create_user(db, "org_gestor", "gestor@ufpi.br")
    u_chefe_unidade = create_user(db, "chefe_unidade", "chefe@ufpi.br")
    u_grupo_gestor = create_user(db, "grupo_gestor", "gestor_grupo@ufpi.br")
    u_participante = create_user(db, "participante", "participante@ufpi.br")
    u_estranho = create_user(db, "estranho", "estranho@ufpi.br")

    # Vínculo da Org
    db.add(UsuarioOrganizacao(id_organizacao=org.id, id_usuario=u_org_gestor.id, papel_organizacao=PapelOrganizacaoEnum.GESTOR))
    db.add(UsuarioOrganizacao(id_organizacao=org.id, id_usuario=u_chefe_unidade.id, papel_organizacao=PapelOrganizacaoEnum.MEMBRO))
    db.add(UsuarioOrganizacao(id_organizacao=org.id, id_usuario=u_grupo_gestor.id, papel_organizacao=PapelOrganizacaoEnum.MEMBRO))
    db.add(UsuarioOrganizacao(id_organizacao=org.id, id_usuario=u_participante.id, papel_organizacao=PapelOrganizacaoEnum.MEMBRO))
    db.add(UsuarioOrganizacao(id_organizacao=org.id, id_usuario=u_estranho.id, papel_organizacao=PapelOrganizacaoEnum.MEMBRO))
    db.commit()

    # Chefe da Unidade
    db.add(Perfil(id_unidade=unidade.id, id_usuario=u_chefe_unidade.id, id_nivel=nivel_chefe_unidade.id))
    # Atribuições no Grupo: u_grupo_gestor é 201, u_participante é 202
    db.add(Atribuicao(id_grupo=grupo.id, id_usuario=u_grupo_gestor.id, id_nivel=nivel_gestor_grupo.id))
    db.add(Atribuicao(id_grupo=grupo.id, id_usuario=u_participante.id, id_nivel=nivel_participante.id))
    db.commit()

    # --- CENÁRIO 1: USUÁRIO SEM ACESSO AO GRUPO (u_estranho) ---
    assert daily_permission_service.check_user_can_access_group(db, u_estranho, grupo.id) is False
    assert daily_permission_service.check_user_can_access_config(db, u_estranho, config.id) is False
    assert daily_permission_service.check_user_can_edit_config(db, u_estranho, grupo.id) is False

    with pytest.raises(HTTPException) as exc:
        daily_permission_service.require_group_access(db, u_estranho, grupo.id)
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        daily_permission_service.require_config_access(db, u_estranho, config.id)
    assert exc.value.status_code == 403

    with pytest.raises(HTTPException) as exc:
        daily_permission_service.require_config_edit_access(db, u_estranho, grupo.id)
    assert exc.value.status_code == 403

    # --- CENÁRIO 2: PARTICIPANTE DO GRUPO (u_participante) ---
    # Tem acesso para visualizar dailies e itens do grupo
    assert daily_permission_service.check_user_can_access_group(db, u_participante, grupo.id) is True
    assert daily_permission_service.check_user_can_access_config(db, u_participante, config.id) is True
    daily_permission_service.require_group_access(db, u_participante, grupo.id)
    daily_permission_service.require_config_access(db, u_participante, config.id)

    # canEditConfig deve ser False para participante comum
    res_part = daily_config_service.get_config_by_group(db, grupo.id, u_participante)
    assert res_part["canEditConfig"] is False
    assert daily_permission_service.check_user_can_edit_config(db, u_participante, grupo.id) is False

    # Participante não pode editar configuração (403)
    with pytest.raises(HTTPException) as exc:
        daily_permission_service.require_config_edit_access(db, u_participante, grupo.id)
    assert exc.value.status_code == 403

    # --- CENÁRIO 3: GESTOR DO GRUPO (u_grupo_gestor) ---
    assert daily_permission_service.check_user_can_access_group(db, u_grupo_gestor, grupo.id) is True
    assert daily_permission_service.check_user_can_access_config(db, u_grupo_gestor, config.id) is True
    assert daily_permission_service.check_user_can_edit_config(db, u_grupo_gestor, grupo.id) is True
    daily_permission_service.require_config_edit_access(db, u_grupo_gestor, grupo.id)

    res_gestor = daily_config_service.get_config_by_group(db, grupo.id, u_grupo_gestor)
    assert res_gestor["canEditConfig"] is True

    # Gestor do grupo pode atualizar a configuração
    updated = daily_config_service.update_config(db, config.id, DiarioConfigUpdate(periodo_addnota_inicio="09:00"))
    assert updated["periodo_addnota_inicio"] == "09:00"
    assert len(updated["grupo"]["usuarios_chefes"]) == 1
    assert updated["grupo"]["usuarios_chefes"][0]["id"] == str(u_grupo_gestor.id)
    assert any(a["isLeader"] is True and a["id_usuario"] == str(u_grupo_gestor.id) for a in updated["grupo"]["atribuicoes"])

    # --- CENÁRIO 4: CHEFE DA UNIDADE (u_chefe_unidade) ---
    assert daily_permission_service.check_user_can_access_group(db, u_chefe_unidade, grupo.id) is True
    assert daily_permission_service.check_user_can_edit_config(db, u_chefe_unidade, grupo.id) is True

    # --- CENÁRIO 5: GESTOR DA ORGANIZAÇÃO (u_org_gestor) ---
    assert daily_permission_service.check_user_can_access_group(db, u_org_gestor, grupo.id) is True
    assert daily_permission_service.check_user_can_access_config(db, u_org_gestor, config.id) is True
    assert daily_permission_service.check_user_can_edit_config(db, u_org_gestor, grupo.id) is True
    daily_permission_service.require_config_edit_access(db, u_org_gestor, grupo.id)

    res_org = daily_config_service.get_config_by_group(db, grupo.id, u_org_gestor)
    assert res_org["canEditConfig"] is True

    # --- CENÁRIO 6: ADMIN GLOBAL (u_admin) ---
    assert daily_permission_service.check_user_can_access_group(db, u_admin, grupo.id) is True
    assert daily_permission_service.check_user_can_access_config(db, u_admin, config.id) is True
    assert daily_permission_service.check_user_can_edit_config(db, u_admin, grupo.id) is True
    daily_permission_service.require_config_edit_access(db, u_admin, grupo.id)

    res_admin = daily_config_service.get_config_by_group(db, grupo.id, u_admin)
    assert res_admin["canEditConfig"] is True


def test_grupo_chefes_registradores_config(db):
    from app.schemas.grupo import GrupoCreate, GrupoUpdate
    from app.services import grupo_service

    # Setup Níveis
    nivel_gestor = Nivel(valor=NivelCodigoEnum.GESTOR_GRUPO.value, nome="Gestor de Grupo", tipo=TipoNivelEnum.ATRIBUICAO)
    nivel_part = Nivel(valor=NivelCodigoEnum.PARTICIPANTE.value, nome="Participante", tipo=TipoNivelEnum.ATRIBUICAO)
    db.add_all([nivel_gestor, nivel_part])
    db.commit()

    org = Organizacao(nome="Org Registradores", sigla="OR")
    db.add(org)
    db.commit()

    unidade = Unidade(nome="Unidade X", id_organizacao=org.id)
    db.add(unidade)
    db.commit()

    chefe_1 = create_user(db, "chefe_nao_reg", "chefe1@org.com")
    chefe_2 = create_user(db, "chefe_reg", "chefe2@org.com")
    participante = create_user(db, "part_1", "part1@org.com")

    for u in [chefe_1, chefe_2, participante]:
        db.add(UsuarioOrganizacao(id_usuario=u.id, id_organizacao=org.id, papel_organizacao=PapelOrganizacaoEnum.MEMBRO, inativo=False))
    db.commit()

    # Cria grupo: chefe_1 não registrador (default), chefe_2 é registrador
    grupo = grupo_service.create_in_unidade(
        db,
        unidade.id,
        GrupoCreate(
            nome="Grupo Teste Chefes",
            id_unidade=unidade.id,
            usuarios_chefes=[chefe_1.id, chefe_2.id],
            usuarios_participantes=[participante.id],
            chefes_registradores=[chefe_2.id],
        )
    )

    atribs = {str(a.id_usuario): a for a in db.query(Atribuicao).filter(Atribuicao.id_grupo == grupo.id, Atribuicao.inativo == False).all()}
    assert atribs[str(chefe_1.id)].registrador is False
    assert atribs[str(chefe_2.id)].registrador is True
    assert atribs[str(participante.id)].registrador is True

    # Atualiza grupo: torna chefe_1 registrador e remove chefe_2 de registrador
    grupo_service.update_in_unidade(
        db,
        unidade.id,
        grupo.id,
        GrupoUpdate(
            usuarios_chefes=[chefe_1.id, chefe_2.id],
            usuarios_participantes=[participante.id],
            chefes_registradores=[chefe_1.id],
        )
    )

    atribs_updated = {str(a.id_usuario): a for a in db.query(Atribuicao).filter(Atribuicao.id_grupo == grupo.id, Atribuicao.inativo == False).all()}
    assert atribs_updated[str(chefe_1.id)].registrador is True
    assert atribs_updated[str(chefe_2.id)].registrador is False
    assert atribs_updated[str(participante.id)].registrador is True


def test_daily_item_yesterday_required(db):
    from app.schemas.daily import AnotacaoCreate, DiarioItemCreate
    from app.services import daily_item_service
    from app.core.timezone import now_in_app_timezone

    nivel_part = Nivel(valor=NivelCodigoEnum.PARTICIPANTE.value, nome="Participante", tipo=TipoNivelEnum.ATRIBUICAO)
    nivel_gestor = Nivel(valor=NivelCodigoEnum.GESTOR_GRUPO.value, nome="Gestor de Grupo", tipo=TipoNivelEnum.ATRIBUICAO)
    db.add_all([nivel_part, nivel_gestor])
    db.commit()

    org = Organizacao(nome="Org Daily Test", sigla="ODT")
    db.add(org)
    db.commit()

    unidade = Unidade(nome="Unidade Daily", id_organizacao=org.id)
    db.add(unidade)
    db.commit()

    grupo = GrupoTrabalho(nome="Grupo Daily", id_unidade=unidade.id, id_organizacao=org.id)
    db.add(grupo)
    db.commit()

    config = DiarioConfig(id_grupo=grupo.id, periodo_addnota_inicio="00:00", periodo_addnota_fim="23:59")
    db.add(config)
    db.commit()

    user = create_user(db, "user_daily", "user_daily@org.com")
    db.add(UsuarioOrganizacao(id_usuario=user.id, id_organizacao=org.id, papel_organizacao=PapelOrganizacaoEnum.MEMBRO, inativo=False))
    db.add(Atribuicao(id_grupo=grupo.id, id_usuario=user.id, id_nivel=nivel_part.id, registrador=True))
    db.commit()

    now = now_in_app_timezone()

    # Tentativa de salvar sem YESTERDAY -> Deve lançar 400
    invalid_payload = DiarioItemCreate(
        notas={
            "TODAY": [AnotacaoCreate(descricao="Fiz algo hoje")],
            "YESTERDAY": [],
        }
    )
    with pytest.raises(HTTPException) as exc_info:
        daily_item_service.create_item(db, config.id, now.year, now.month, now.day, invalid_payload, user)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "daily_item.yesterday_required"

    # Tentativa de salvar com YESTERDAY vazio -> Deve lançar 400
    invalid_blank_payload = DiarioItemCreate(
        notas={
            "YESTERDAY": [AnotacaoCreate(descricao="   ")],
        }
    )
    with pytest.raises(HTTPException) as exc_info:
        daily_item_service.create_item(db, config.id, now.year, now.month, now.day, invalid_blank_payload, user)
    assert exc_info.value.status_code == 400

    # Tentativa de salvar sem TODAY -> Deve lançar 400
    invalid_no_today_payload = DiarioItemCreate(
        notas={
            "YESTERDAY": [AnotacaoCreate(descricao="Fiz algo ontem")],
            "TODAY": [],
        }
    )
    with pytest.raises(HTTPException) as exc_info:
        daily_item_service.create_item(db, config.id, now.year, now.month, now.day, invalid_no_today_payload, user)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "daily_item.today_required"

    # Salvando com YESTERDAY e TODAY preenchidos -> Sucesso
    valid_payload = DiarioItemCreate(
        notas={
            "YESTERDAY": [AnotacaoCreate(descricao="Trabalhei na tarefa ontem")],
            "TODAY": [AnotacaoCreate(descricao="Continuarei hoje")],
        }
    )
    item = daily_item_service.create_item(db, config.id, now.year, now.month, now.day, valid_payload, user)
    assert item is not None
    assert len(item.notas) == 2
