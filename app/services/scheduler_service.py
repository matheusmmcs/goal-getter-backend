import logging
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
import httpx

from app.core.database import SessionLocal
from app.core.timezone import now_in_app_timezone
from app.models.agendamento import Agendamento
from app.models.agendamento_historico import AgendamentoHistorico

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def execute_agendamento_job(agendamento_id: str):
    """Callback function executed by the scheduler for a scheduled job."""
    db: Session = SessionLocal()
    try:
        agendamento = db.query(Agendamento).filter(
            Agendamento.id == agendamento_id,
            Agendamento.ativo == True,
            Agendamento.inativo == False
        ).first()

        if not agendamento:
            logger.warning(f"Agendamento {agendamento_id} não encontrado ou inativo. Ignorando execução.")
            return

        success = True
        detalhes = f"Notificação executada com sucesso. Canal: {agendamento.canal}"

        # If canal is a URL (webhook), send HTTP POST request
        if agendamento.canal and agendamento.canal.startswith("http"):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(agendamento.canal, json={"text": agendamento.mensagem})
                    if resp.status_code >= 400:
                        success = False
                        detalhes = f"Erro HTTP {resp.status_code}: {resp.text}"
            except Exception as ex:
                success = False
                detalhes = f"Erro ao enviar webhook: {str(ex)}"
        else:
            logger.info(f"Agendamento {agendamento.id}: Mensagem '{agendamento.mensagem}' pronta para canal '{agendamento.canal}'.")

        # Record execution history
        historico = AgendamentoHistorico(
            id_agendamento=agendamento.id,
            data_envio=now_in_app_timezone(),
            sucesso=success,
            detalhes=detalhes
        )
        db.add(historico)
        db.commit()
        logger.info(f"Histórico registrado para o agendamento {agendamento_id}. Sucesso: {success}")
    except Exception as e:
        logger.error(f"Erro ao executar job de agendamento {agendamento_id}: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()


def load_and_schedule_jobs():
    """Loads active agendamentos from DB and schedules them in APScheduler."""
    db: Session = SessionLocal()
    try:
        agendamentos = db.query(Agendamento).filter(
            Agendamento.ativo == True,
            Agendamento.inativo == False
        ).all()

        for ag in agendamentos:
            if ag.expressao_cron:
                try:
                    trigger = CronTrigger.from_crontab(ag.expressao_cron)
                    scheduler.add_job(
                        execute_agendamento_job,
                        trigger=trigger,
                        args=[str(ag.id)],
                        id=str(ag.id),
                        replace_existing=True
                    )
                    logger.info(f"Agendamento {ag.id} agendado via Cron ({ag.expressao_cron}).")
                except Exception as ex:
                    logger.error(f"Falha ao criar CronTrigger para {ag.id} ({ag.expressao_cron}): {ex}")
    except Exception as e:
        logger.error(f"Erro ao carregar agendamentos do banco de dados: {e}")
    finally:
        db.close()


def start_scheduler():
    """Starts the APScheduler instance and loads database jobs."""
    if not scheduler.running:
        scheduler.start()
        logger.info("APScheduler iniciado com sucesso.")
        load_and_schedule_jobs()


def shutdown_scheduler():
    """Shuts down the APScheduler instance gracefully."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("APScheduler encerrado com sucesso.")
