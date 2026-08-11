import logging
from app.core.database import SessionLocal
from app.models.enums import TipoNivelEnum, NivelCodigoEnum
from app.models.nivel import Nivel
from app.models.usuario import Usuario
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)

def run_seed():
    db = SessionLocal()
    try:
        # Seed Niveis
        niveis_defaults = [
            {"nome": "Chefe de Unidade", "tipo": TipoNivelEnum.PERFIL, "valor": NivelCodigoEnum.CHEFE_UNIDADE.value},
            {"nome": "Gestor de Grupo", "tipo": TipoNivelEnum.ATRIBUICAO, "valor": NivelCodigoEnum.GESTOR_GRUPO.value},
            {"nome": "Participante", "tipo": TipoNivelEnum.ATRIBUICAO, "valor": NivelCodigoEnum.PARTICIPANTE.value},
        ]
        
        for n_def in niveis_defaults:
            existing_nivel = db.query(Nivel).filter(Nivel.valor == n_def["valor"]).first()
            if not existing_nivel:
                novo_nivel = Nivel(**n_def)
                db.add(novo_nivel)
                logger.info(f"Seeded Nivel: {n_def['nome']}")
        
        # Seed Admin User
        admin_usuario = db.query(Usuario).filter(Usuario.usuario == 'admin').first()
        if not admin_usuario:
            novo_admin = Usuario(
                usuario='admin',
                senha=get_password_hash('admin'),
                nome='Administrador',
                is_admin=True,
                is_autorizado=True
            )
            db.add(novo_admin)
            logger.info("Seeded admin user")
            
        # Seed Default Organization
        from app.models.organizacao import Organizacao
        from app.models.usuario_organizacao import UsuarioOrganizacao
        from app.models.unidade import Unidade
        from app.models.grupo import GrupoTrabalho
        from app.models.enums import PapelOrganizacaoEnum

        default_org = db.query(Organizacao).filter(Organizacao.nome == "UFPI").first()
        if not default_org:
            default_org = Organizacao(
                nome="UFPI",
                sigla="UFPI",
                descricao="Universidade Federal do Piauí"
            )
            db.add(default_org)
            db.flush()
            logger.info("Seeded default Organizacao: UFPI")

        if admin_usuario:
            admin_vinculo = db.query(UsuarioOrganizacao).filter(
                UsuarioOrganizacao.id_organizacao == default_org.id,
                UsuarioOrganizacao.id_usuario == admin_usuario.id
            ).first()
            if not admin_vinculo:
                admin_vinculo = UsuarioOrganizacao(
                    id_organizacao=default_org.id,
                    id_usuario=admin_usuario.id,
                    papel_organizacao=PapelOrganizacaoEnum.GESTOR
                )
                db.add(admin_vinculo)

        # Vincular unidades e grupos orfãos à organização padrão
        db.query(Unidade).filter(Unidade.id_organizacao.is_(None)).update({"id_organizacao": default_org.id}, synchronize_session=False)
        db.query(GrupoTrabalho).filter(GrupoTrabalho.id_organizacao.is_(None)).update({"id_organizacao": default_org.id}, synchronize_session=False)

        db.commit()
    except Exception as e:
        logger.error(f"Error during seeding: {e}")
        db.rollback()
    finally:
        db.close()

