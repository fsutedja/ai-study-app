import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from database import engine
from dependencies import get_current_user
from typing import Optional, Dict

router = APIRouter(prefix="/nodes", tags=["questions"])


class QuestionCreate(BaseModel):
    prompt: str
    question_type: str
    options: Optional[Dict] = None
    correct_answer: Optional[str] = None
    difficulty: int = 1


@router.post("/{node_id}/questions")
def create_question(
    node_id: str,
    data: QuestionCreate,
    current_user: dict = Depends(get_current_user)
):
    ownership_check = text("""
        SELECT n.id
        FROM learning_nodes n
        JOIN learning_paths p ON n.path_id = p.id
        WHERE n.id = :node_id AND p.user_id = :user_id
    """)

    with engine.connect() as conn:
        owner = conn.execute(
            ownership_check,
            {
                "node_id": node_id,
                "user_id": current_user["sub"]
            }
        ).fetchone()

    if not owner:
        raise HTTPException(status_code=404, detail="Node not found")

    insert_query = text("""
        INSERT INTO learning_questions
        (node_id, prompt, question_type, options, correct_answer, difficulty)
        VALUES
        (:node_id, :prompt, :question_type, :options, :correct_answer, :difficulty)
        RETURNING id, prompt, question_type, options, difficulty
    """)

    with engine.begin() as conn:
        question = conn.execute(
            insert_query,
            {
                "node_id": node_id,
                "prompt": data.prompt,
                "question_type": data.question_type,
                "options": json.dumps(data.options) if data.options else None,
                "correct_answer": data.correct_answer,
                "difficulty": data.difficulty
            }
        ).mappings().fetchone()

    return dict(question)


@router.get("/{node_id}/questions")
def list_questions(
    node_id: str,
    current_user: dict = Depends(get_current_user)
):
    query = text("""
        SELECT q.id, q.prompt, q.question_type, q.options, q.difficulty
        FROM learning_questions q
        JOIN learning_nodes n ON q.node_id = n.id
        JOIN learning_paths p ON n.path_id = p.id
        WHERE q.node_id = :node_id AND p.user_id = :user_id
        ORDER BY q.created_at ASC
    """)

    with engine.connect() as conn:
        questions = conn.execute(
            query,
            {
                "node_id": node_id,
                "user_id": current_user["sub"]
            }
        ).mappings().fetchall()

    return [dict(q) for q in questions]