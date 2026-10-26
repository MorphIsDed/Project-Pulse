import sqlite3

from flask import Blueprint, jsonify, request, session
from werkzeug.security import generate_password_hash, check_password_hash

from app import get_db

auth_api = Blueprint("auth_api", __name__, url_prefix="/api/v1/auth")


@auth_api.post("/register")
def register():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify(
            error={"code": "invalid_json", "message": "Send a JSON object."}
        ), 400

    email = data.get("email")
    password = data.get("password")
    display_name = data.get("display_name")

    if not all(isinstance(value, str) for value in (email, password, display_name)):
        return jsonify(
            error={
                "code": "missing_fields",
                "message": "Email, password, and display name are required.",
            }
        ), 400

    email = email.strip().lower()
    display_name = display_name.strip()

    if "@" not in email or any(char.isspace() for char in email):
        return jsonify(
            error={"code": "invalid_email", "message": "Enter a valid email address."}
        ), 400

    if len(password) < 8:
        return jsonify(
            error={
                "code": "weak_password",
                "message": "Password must be at least 8 characters.",
            }
        ), 400

    if not display_name:
        return jsonify(
            error={
                "code": "invalid_display_name",
                "message": "Display name cannot be empty.",
            }
        ), 400

    password_hash = generate_password_hash(password)

    try:
        db = get_db()
        cursor = db.execute(
            """
            INSERT INTO users (email, password_hash, display_name)
            VALUES (?, ?, ?)
            """,
            (email, password_hash, display_name),
        )
        db.commit()
    except sqlite3.IntegrityError:
        get_db().rollback()
        return jsonify(
            error={
                "code": "email_conflict",
                "message": "That email is already registered.",
            }
        ), 409

    return jsonify(
        user={
            "id": cursor.lastrowid,
            "email": email,
            "display_name": display_name,
        }
    ), 201
    

@auth_api.post("/login")
def login():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify(
            error={"code": "invalid_json", "message": "Send a JSON object."}
        ), 400

    email = data.get("email")
    password = data.get("password")

    if not isinstance(email, str) or not isinstance(password, str):
        return jsonify(
            error={"code": "missing_fields", "message": "Email and password are required."}
        ), 400

    user = get_db().execute(
        """
        SELECT id, email, password_hash, display_name
        FROM users
        WHERE email = ?
        """,
        (email.strip().lower(),),
    ).fetchone()

    if user is None or not check_password_hash(user["password_hash"], password):
        return jsonify(
            error={"code": "invalid_credentials", "message": "Email or password is incorrect."}
        ), 401

    session.clear()
    session["user_id"] = user["id"]

    return jsonify(
        user={
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
        }
    ), 200


@auth_api.post("/logout")
def logout():
    session.clear()
    return "", 204


@auth_api.get("/me")
def current_user():
    user_id = session.get("user_id")

    if user_id is None:
        return jsonify(
            error={"code": "not_authenticated", "message": "Please log in."}
        ), 401

    user = get_db().execute(
        """
        SELECT id, email, display_name
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    if user is None:
        session.clear()
        return jsonify(
            error={"code": "not_authenticated", "message": "Please log in again."}
        ), 401

    return jsonify(
        user={
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
        }
    ), 200