from uuid import UUID
from typing import Optional
from pydantic import BaseModel

class LoginRequest(BaseModel):
    usuario: str
    senha: str

class UserInfo(BaseModel):
    id: UUID
    nome: str
    usuario: str
    email: Optional[str] = None
    cpf: Optional[str] = None
    is_admin: bool
    perfis: list = []

class TokenData(BaseModel):
    token: str
    user: UserInfo

class LoginResponse(BaseModel):
    success: bool
    message: str
    data: TokenData
