"""
Auth Router - JWT login, register, token refresh
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import Optional
import jwt
import bcrypt

from backend.database import get_db, User
from backend.config import settings

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# Pydantic Schemas
class UserRegister(BaseModel):
      email: EmailStr
      password: str
      full_name: Optional[str] = None


class Token(BaseModel):
      access_token: str
      token_type: str = "bearer"


# Helpers
def hash_password(password: str) -> str:
      return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
      return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict) -> str:
      to_encode = data.copy()
      expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
      to_encode.update({"exp": expire})
      return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
      try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                user_id = payload.get("sub")
                if not user_id:
                              raise HTTPException(status_code=401, detail="Invalid token")
                          result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if not user:
                              raise HTTPException(status_code=401, detail="User not found")
                          return user
            except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")


# Routes
@router.post("/register", response_model=Token)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
      result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
              raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
              email=user_data.email,
              hashed_password=hash_password(user_data.password),
              full_name=user_data.full_name,
          )
    db.add(user)
    await db.flush()
    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token)


@router.post("/login", response_model=Token)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
      result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
              raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token)


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
      return {"id": str(current_user.id), "email": current_user.email, "name": current_user.full_name}
