import sqlite3

from flask import Blueprint, jsonify, request, session

from app import get_db

organizations_api = Blueprint(
    "organizations_api",
    __name__,
    url_prefix="/api/v1/organizations",
)


@organizations_api.get("")
def list_organizations():
    user_id = session.get("user_id")

    if user_id is None:
        return jsonify(
            error={"code": "not_authenticated", "message": "Please log in."}
        ), 401

    try:
        limit = min(max(int(request.args.get("limit", 50)), 1), 100)
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError:
        return jsonify(
            error={"code": "invalid_pagination", "message": "Limit and offset must be numbers."}
        ), 400

    rows = get_db().execute(
        """
        SELECT o.id, o.name, o.created_at, m.role
        FROM organizations AS o
        JOIN organization_memberships AS m
          ON m.organization_id = o.id
        WHERE m.user_id = ?
        ORDER BY o.name
        LIMIT ? OFFSET ?
        """,
        (user_id, limit, offset),
    ).fetchall()

    return jsonify(
        organizations=[
            {
                "id": row["id"],
                "name": row["name"],
                "created_at": row["created_at"],
                "role": row["role"],
            }
            for row in rows
        ],
        limit=limit,
        offset=offset,
    ), 200


@organizations_api.post("")
def create_organization():
    user_id = session.get("user_id")

    if user_id is None:
        return jsonify(
            error={"code": "not_authenticated", "message": "Please log in."}
        ), 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify(
            error={"code": "invalid_json", "message": "Send a JSON object."}
        ), 400

    name = data.get("name")

    if not isinstance(name, str) or not name.strip():
        return jsonify(
            error={"code": "invalid_name", "message": "Organization name is required."}
        ), 400

    name = name.strip()

    if len(name) > 120:
        return jsonify(
            error={"code": "invalid_name", "message": "Name must be 120 characters or fewer."}
        ), 400

    db = get_db()

    try:
        cursor = db.execute(
            "INSERT INTO organizations (name) VALUES (?)",
            (name,),
        )
        organization_id = cursor.lastrowid

        db.execute(
            """
            INSERT INTO organization_memberships (organization_id, user_id, role)
            VALUES (?, ?, 'owner')
            """,
            (organization_id, user_id),
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        return jsonify(
            error={
                "code": "organization_creation_failed",
                "message": "Could not create the organization.",
            }
        ), 400

    return jsonify(
        organization={
            "id": organization_id,
            "name": name,
            "role": "owner",
        }
    ), 201