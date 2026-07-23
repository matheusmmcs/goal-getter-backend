import os
import sys
import logging
from logging.handlers import TimedRotatingFileHandler
from app.core.config import settings

def setup_logging():
    if not settings.BACKEND_LOGS_ENABLED:
        logging.disable(logging.CRITICAL)
        return

    log_level = getattr(logging, settings.BACKEND_LOG_LEVEL.upper(), logging.INFO)
    logger = logging.getLogger()
    logger.setLevel(log_level)

    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter(
        '{"time": "%(asctime)s", "level": "%(levelname)s", "module": "%(module)s", "message": "%(message)s"}'
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)

    if not os.path.exists(settings.BACKEND_LOG_DIR):
        os.makedirs(settings.BACKEND_LOG_DIR)
        
    log_file = os.path.join(settings.BACKEND_LOG_DIR, 'app.log')
    file_handler = TimedRotatingFileHandler(
        log_file, when='midnight', interval=1, backupCount=settings.BACKEND_LOG_RETENTION_DAYS, encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
