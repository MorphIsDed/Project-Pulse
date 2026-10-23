import click
from flask import Flask
from flask.cli import with_appcontext

from app.errors import ApiError
from app.services.identity import seed_demo_users


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
