from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr, Field
from passlib.context import CryptContext
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from database import engine

from jwt_utils import create_access_token
from dependencies import get_current_user

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return pwd_context.hash(password_bytes)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return pwd_context.verify(password_bytes, hashed_password)


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/signup")
def signup(data: SignupRequest):
    hashed = hash_password(data.password)

    query = text("""
        INSERT INTO app_users (email, password_hash)
        VALUES (:email, :password_hash)
    """)

    try:
        with engine.begin() as conn:
            conn.execute(query, {
                "email": data.email,
                "password_hash": hashed
            })
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Email already exists")

    return {"message": "User created successfully"}


@router.post("/login")
def login(data: LoginRequest):
    query = text("""
        SELECT id, password_hash
        FROM app_users
        WHERE email = :email
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {"email": data.email}).fetchone()

    if not result:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_id, password_hash = result

    if not verify_password(data.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": str(user_id)})

    return {
        "access_token": token,
        "token_type": "bearer"
    }


@router.get("/me")
def read_me(current_user: dict = Depends(get_current_user)):
    return {"user_id": current_user["sub"]}