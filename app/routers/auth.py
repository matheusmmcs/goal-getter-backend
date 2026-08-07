from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.response import success_response
from app.schemas.auth import LoginRequest
from app.services import auth_service

router = APIRouter(tags=["Auth"])

@router.post("/login")
def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    result = auth_service.login(db, credentials)
    return success_response(data=result, message="auth.login_success")
