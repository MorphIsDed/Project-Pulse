import sqlite3

from flask import Blueprint, jsonify, request
from werkzeug.security import generate_password_hash

from app import get_db

auth_api = Blueprint("auth_api", __name__, url_prefix="/api/v1/auth")


@auth_api.post("/register")
def register():
    data = request.get_json(silent=True)
    
    if not isinstance(data, dict):
        return jsonify(error={"code": "invalid_json", "message": "Send a JSON object"}), 400

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
        return jsonify(error={"code": "invalid email", "message": "Enter a valid email adderess"}), 400 

    if len(password) < 8:
        return jsonify(error={"code": "weak_password", "message": "Password must be atleast 8 characters"}), 400
    
    if not display_name:
        return jsonify({"code": "invalid_display_name", "message": "Display name cannot be empty"}), 400
    
    password_hash = generate_password_hash(password)
    # 4. Insert the new user into the database.
    #    The email UNIQUE constraint can detect duplicates.

    # 5. Return only safe user fields (for example: id, email,
    #    display_name) with HTTP 201.
    pass