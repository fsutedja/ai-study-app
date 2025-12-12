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


class QuestionAttempt(BaseModel):
    answer: str

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

@router.post("/questions/{question_id}/attempt")
def submit_question_attempt(
    question_id: str,
    data: QuestionAttempt,
    current_user: dict = Depends(get_current_user)
):
    # 1. Verify ownership + get correct answer
    fetch_question = text("""
        SELECT q.correct_answer, q.node_id
        FROM learning_questions q
        JOIN learning_nodes n ON q.node_id = n.id
        JOIN learning_paths p ON n.path_id = p.id
        WHERE q.id = :question_id
        AND p.user_id = :user_id
    """)

    with engine.connect() as conn:
        question = conn.execute(
            fetch_question,
            {
                "question_id": question_id,
                "user_id": current_user["sub"]
            }
        ).fetchone()

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # 2. Block multiple attempts
    attempt_check = text("""
        SELECT 1
        FROM learning_question_attempts
        WHERE question_id = :question_id
        AND user_id = :user_id
    """)

    with engine.connect() as conn:
        existing = conn.execute(
            attempt_check,
            {
                "question_id": question_id,
                "user_id": current_user["sub"]
            }
        ).fetchone()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="You have already attempted this question"
        )

    # 3. Grade
    is_correct = data.answer == question.correct_answer

    # 4. Store attempt
    insert_attempt = text("""
        INSERT INTO learning_question_attempts
        (user_id, question_id, is_correct)
        VALUES
        (:user_id, :question_id, :is_correct)
    """)

    with engine.begin() as conn:
        conn.execute(
            insert_attempt,
            {
                "user_id": current_user["sub"],
                "question_id": question_id,
                "is_correct": is_correct
            }
        )

    # 5. Recalculate mastery (AFTER storing attempt)
    progress_query = text("""
        SELECT
            COUNT(q.id) AS total,
            SUM(CASE WHEN a.is_correct THEN 1 ELSE 0 END) AS correct
        FROM learning_questions q
        LEFT JOIN learning_question_attempts a
            ON q.id = a.question_id AND a.user_id = :user_id
        WHERE q.node_id = :node_id
    """)

    with engine.connect() as conn:
        stats = conn.execute(
            progress_query,
            {
                "node_id": question.node_id,
                "user_id": current_user["sub"]
            }
        ).fetchone()

    total = stats.total or 0
    correct = stats.correct or 0
    mastery = (correct / total) if total > 0 else 0.0

    return {
        "question_id": question_id,
        "submitted_answer": data.answer,
        "correct": is_correct,
        "mastery": round(mastery, 2),
        "completed": mastery >= 0.8
    }