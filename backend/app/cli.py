import click
from datetime import datetime, timezone

from flask import Flask
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from app import get_db
from app.errors import ApiError
from app.services.identity import (
    seed_demo_users,
    normalize_email,
    validate_display_name,
    validate_password,
)


def register_cli(app: Flask) -> None:
    @app.cli.command("seed-demo")
    @click.option(
        "--force",
        is_flag=True,
        help="Allow demo seeding when APP_ENV=production.",
    )
    @with_appcontext
    def seed_demo(force: bool) -> None:
        if app.config.get("APP_ENV") == "production" and not force:
            raise click.ClickException(
                "Refusing to seed demo accounts in production. "
                "Use --force to override."
            )

        try:
            created, skipped = seed_demo_users(app.config["DEMO_PASSWORD"])
        except (ApiError, ValueError) as exc:
            message = exc.message if isinstance(exc, ApiError) else str(exc)
            raise click.ClickException(message) from exc

        click.echo(
            f"Demo accounts: {created} created, {skipped} skipped. "
            "Organization and workspace memberships arrive in M2."
        )

    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--display-name", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    @with_appcontext
    def create_admin(email: str, display_name: str, password: str) -> None:
        """Create the first verified owner on a new installation."""
        try:
            normalized_email = normalize_email(email)
            name = validate_display_name(display_name)
        except ApiError as exc:
            raise click.ClickException(exc.message) from exc
        if len(password) < 10 or len(password) > 128:
            raise click.ClickException("Use a password between 10 and 128 characters.")
        try:
            valid_password = validate_password(password)
        except ApiError as exc:
            raise click.ClickException(exc.message) from exc
        db = get_db()
        try:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
                raise click.ClickException(
                    "Initial admin setup is only available while the database has no users."
                )
            cursor = db.execute(
                "INSERT INTO users(email,password_hash,display_name,email_verified_at) VALUES(?,?,?,?)",
                (
                    normalized_email,
                    generate_password_hash(valid_password),
                    name,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            org = db.execute("INSERT INTO organizations(name) VALUES(?)", (f"{name}'s organization",))
            db.execute(
                "INSERT INTO organization_memberships(organization_id,user_id,role) VALUES(?,?,'owner')",
                (org.lastrowid, cursor.lastrowid),
            )
            db.execute(
                "INSERT INTO workspaces(organization_id,name) VALUES(?,?)",
                (org.lastrowid, "My workspace"),
            )
            db.commit()
        except click.ClickException:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            raise click.ClickException(f"Initial admin setup failed: {exc}") from exc
        click.echo("Initial owner account and workspace created. Sign in with the account you entered.")
