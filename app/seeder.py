import logging
from app.core.database import SessionLocal
from app.models.nivel import Nivel, TipoNivelEnum
from app.models.usuario import Usuario
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)

def run_seed():
    db = SessionLocal()
    try:
        # Seed Niveis
        niveis_defaults = [
            {"nome": "Chefe de Unidade", "tipo": TipoNivelEnum.PERFIL, "valor": 101},
            {"nome": "Gestor de Grupo", "tipo": TipoNivelEnum.ATRIBUICAO, "valor": 201},
            {"nome": "Participante", "tipo": TipoNivelEnum.ATRIBUICAO, "valor": 202},
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
            
        db.commit()
    except Exception as e:
        logger.error(f"Error during seeding: {e}")
        db.rollback()
    finally:
        db.close()
