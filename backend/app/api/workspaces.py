import sqlite3
from flask import Blueprint, jsonify, request, session
from app import get_db


workspaces_api = Blueprint("workspaces_api", __name__)


def get_membership(organization_id: int, user_id: int):
    return get_db().execute(
        """
        SELECT role
        FROM organization_memberships
        WHERE organization_id = ? AND user_id = ?
        """,
        (organization_id, user_id),
    ).fetchone()


@workspaces_api.get(
    "/api/v1/organizations/<int:organization_id>/workspaces"
)
def list_workspaces(organization_id):
    user_id = session.get("user_id")

    if user_id is None:
        return jsonify(
            error={"code": "not_authenticated", "message": "Please log in."}
        ), 401

    if get_membership(organization_id, user_id) is None:
        return jsonify(
            error={"code": "not_found", "message": "Organization not found."}
        ), 404

    rows = get_db().execute(
        """
        SELECT id, organization_id, name, created_at
        FROM workspaces
        WHERE organization_id = ?
        ORDER BY name
        """,
        (organization_id,),
    ).fetchall()

    return jsonify(
        workspaces=[
            {
                "id": row["id"],
                "organization_id": row["organization_id"],
                "name": row["name"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    ), 200


@workspaces_api.post(
    "/api/v1/organizations/<int:organization_id>/workspaces"
)
def create_workspace(organization_id):
    user_id = session.get("user_id")

    if user_id is None:
        return jsonify(
            error={"code": "not_authenticated", "message": "Please log in."}
        ), 401

    membership = get_membership(organization_id, user_id)

    if membership is None:
        return jsonify(
            error={"code": "not_found", "message": "Organization not found."}
        ), 404

    if membership["role"] not in ("owner", "admin"):
        return jsonify(
            error={"code": "forbidden", "message": "Only owners and admins can create workspaces."}
        ), 403

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify(
            error={"code": "invalid_json", "message": "Send a JSON object."}
        ), 400

    name = data.get("name")

    if not isinstance(name, str) or not name.strip():
        return jsonify(
            error={"code": "invalid_name", "message": "Workspace name is required."}
        ), 400

    name = name.strip()

    if len(name) > 120:
        return jsonify(
            error={"code": "invalid_name", "message": "Name must be 120 characters or fewer."}
        ), 400

    db = get_db()

    try:
        cursor = db.execute(
            """
            INSERT INTO workspaces (organization_id, name)
            VALUES (?, ?)
            """,
            (organization_id, name),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify(
            error={
                "code": "workspace_conflict",
                "message": "A workspace with that name may already exist.",
            }
        ), 409

    return jsonify(
        workspace={
            "id": cursor.lastrowid,
            "organization_id": organization_id,
            "name": name,
        }
    ), 201