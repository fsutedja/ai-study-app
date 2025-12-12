from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from database import engine
from dependencies import get_current_user

router = APIRouter(prefix="/paths", tags=["nodes"])

class NodeCreate(BaseModel):
    type: str
    position: int


@router.post("/{path_id}/nodes")
def create_node(
    path_id: str,
    data: NodeCreate,
    current_user: dict = Depends(get_current_user)
):
    # Verify the path belongs to the user
    check_query = text("""
        SELECT id
        FROM learning_paths
        WHERE id = :path_id AND user_id = :user_id
    """)

    with engine.connect() as conn:
        owner = conn.execute(check_query, {
            "path_id": path_id,
            "user_id": current_user["sub"]
        }).fetchone()

    if not owner:
        raise HTTPException(status_code=404, detail="Path not found")

    insert_query = text("""
        INSERT INTO learning_nodes (path_id, type, position)
        VALUES (:path_id, :type, :position)
        RETURNING id, type, position, status
    """)

    with engine.begin() as conn:
        node = conn.execute(insert_query, {
            "path_id": path_id,
            "type": data.type,
            "position": data.position
        }).fetchone()

    return dict(node)


@router.get("/{path_id}/nodes")
def list_nodes(
    path_id: str,
    current_user: dict = Depends(get_current_user)
):
    query = text("""
        SELECT n.id, n.type, n.position, n.status
        FROM learning_nodes n
        JOIN learning_paths p ON n.path_id = p.id
        WHERE p.id = :path_id AND p.user_id = :user_id
        ORDER BY n.position ASC
    """)

    with engine.connect() as conn:
        nodes = conn.execute(query, {
            "path_id": path_id,
            "user_id": current_user["sub"]
        }).fetchall()

    return [dict(n) for n in nodes]