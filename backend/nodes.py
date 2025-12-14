from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from database import engine
from dependencies import get_current_user

router = APIRouter(prefix="/paths", tags=["nodes"])
progress_router = APIRouter(tags=["nodes"])

@router.post("/{path_id}/nodes")
def create_node(
    path_id: str,
    data: dict,
    current_user: dict = Depends(get_current_user)
):
    ownership_check = text("""
        SELECT id
        FROM learning_paths
        WHERE id = :path_id AND user_id = :user_id
    """)

    with engine.connect() as conn:
        owner = conn.execute(
            ownership_check,
            {
                "path_id": path_id,
                "user_id": current_user["sub"]
            }
        ).fetchone()

    if not owner:
        raise HTTPException(status_code=404, detail="Path not found")

    insert_query = text("""
        INSERT INTO learning_nodes (path_id, type, position)
        VALUES (:path_id, :type, :position)
        RETURNING id, path_id, type, position, status
    """)

    with engine.begin() as conn:
        existing_count = conn.execute(
            text("""
                SELECT COUNT(*) AS cnt
                FROM learning_nodes
                WHERE path_id = :path_id
            """),
            {"path_id": path_id},
        ).mappings().fetchone()

        status_value = "unlocked" if (existing_count["cnt"] or 0) == 0 else "locked"

        node = conn.execute(
            insert_query,
            {
                "path_id": path_id,
                "type": data.get("type", "stage"),
                "position": data["position"],
                "status": status_value
            }
        ).mappings().fetchone()

    return dict(node)

@router.get("/{path_id}/nodes")
def list_nodes(
    path_id: str,
    current_user: dict = Depends(get_current_user)
):
    query = text("""
        SELECT n.id, n.position, n.status
        FROM learning_nodes n
        JOIN learning_paths p ON n.path_id = p.id
        WHERE p.id = :path_id AND p.user_id = :user_id
        ORDER BY n.position ASC
    """)

    with engine.connect() as conn:
        nodes = conn.execute(
            query,
            {
                "path_id": path_id,
                "user_id": current_user["sub"]
            }
        ).mappings().fetchall()

    return [dict(n) for n in nodes]

@router.get("/nodes/{node_id}/progress")
def get_node_progress(
    node_id: str,
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

    progress_query = text("""
        SELECT
            COUNT(DISTINCT q.id) AS total,
            COUNT(DISTINCT qa.question_id) FILTER (WHERE qa.is_correct = true) AS correct
        FROM learning_questions q
        LEFT JOIN learning_question_attempts qa
            ON q.id = qa.question_id AND qa.user_id = :user_id
        WHERE q.node_id = :node_id
    """)

    with engine.connect() as conn:
        result = conn.execute(
            progress_query,
            {
                "node_id": node_id,
                "user_id": current_user["sub"]
            }
        ).fetchone()

    total = result.total or 0
    correct = result.correct or 0
    mastery = (correct / total) if total > 0 else 0.0

    return {
        "node_id": node_id,
        "total_questions": total,
        "correct_answers": correct,
        "mastery": round(mastery, 2),
        "completed": mastery >= 0.8
    }

@progress_router.get("/nodes/{node_id}/progress")
def get_node_progress_v2(
    node_id: str,
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
            {"node_id": node_id, "user_id": current_user["sub"]}
        ).fetchone()

    if not owner:
        raise HTTPException(status_code=404, detail="Node not found")

    progress_query = text("""
        SELECT
            COUNT(DISTINCT q.id) AS total,
            COUNT(DISTINCT qa.question_id) FILTER (WHERE qa.is_correct = true) AS correct
        FROM learning_questions q
        LEFT JOIN learning_question_attempts qa
            ON q.id = qa.question_id AND qa.user_id = :user_id
        WHERE q.node_id = :node_id
    """)

    with engine.connect() as conn:
        result = conn.execute(
            progress_query,
            {"node_id": node_id, "user_id": current_user["sub"]}
        ).fetchone()

    total = result.total or 0
    correct = result.correct or 0
    mastery = (correct / total) if total > 0 else 0.0

    return {
        "node_id": node_id,
        "total_questions": total,
        "correct": correct,
        "mastery": round(mastery, 2),
        "passed": mastery >= 0.8
    }