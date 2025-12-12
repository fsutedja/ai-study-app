from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from database import engine
from dependencies import get_current_user

router = APIRouter(prefix="/paths", tags=["paths"])

class PathCreate(BaseModel):
    title: str
    subject: str

@router.post("/")
def create_path(
    data: PathCreate,
    current_user: dict = Depends(get_current_user)
):
    query = text("""
        INSERT INTO learning_paths (user_id, title, subject)
        VALUES (:user_id, :title, :subject)
        RETURNING id, title, subject
    """)

    with engine.begin() as conn:
        result = conn.execute(
            query,
            {
                "user_id": current_user["sub"],
                "title": data.title,
                "subject": data.subject
            }
        ).fetchone()

    return result._mapping   # ← THIS FIXES THE 500

@router.get("/")
def list_paths(current_user: dict = Depends(get_current_user)):
    query = text("""
        SELECT id, title, subject
        FROM learning_paths
        WHERE user_id = :user_id
        ORDER BY created_at DESC
    """)

    with engine.connect() as conn:
        results = conn.execute(
            query,
            {"user_id": current_user["sub"]}
        ).fetchall()

    return [r._mapping for r in results]   # ← ALSO FIXED