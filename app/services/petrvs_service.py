import httpx
from fastapi import HTTPException
from app.core.config import settings
from datetime import datetime

async def get_entregas(cpf: str):
    if not settings.PETRVS_ENABLED:
        raise HTTPException(status_code=503, detail="Petrvs integration is disabled")
    
    url = f"{settings.PETRVS_API_URL}/entregas?cpf={cpf}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Error fetching from Petrvs")
        return response.json()

async def get_entregas_ativas_hoje(cpf: str):
    if not settings.PETRVS_ENABLED:
        raise HTTPException(status_code=503, detail="Petrvs integration is disabled")
        
    entregas = await get_entregas(cpf)
    hoje = datetime.now().date()
    
    ativas = []
    for e in entregas:
        start_str = e.get('data_inicio')
        end_str = e.get('data_fim')
        if start_str and end_str:
            try:
                start_date = datetime.strptime(start_str[:10], '%Y-%m-%d').date()
                end_date = datetime.strptime(end_str[:10], '%Y-%m-%d').date()
                if start_date <= hoje <= end_date:
                    ativas.append(e)
            except ValueError:
                pass
                
    return ativas
