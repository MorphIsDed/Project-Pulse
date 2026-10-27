import click
from flask import Flask
from flask.cli import with_appcontext

from app.errors import ApiError
from app.services.demo import seed_demo


def register_cli(app: Flask) -> None:
    @app.cli.command("seed-demo")
    @click.option(
        "--force",
        is_flag=True,
        help="Allow demo seeding when APP_ENV=production.",
    )
    @with_appcontext
    def seed_demo_command(force: bool) -> None:
        if app.config.get("APP_ENV") == "production" and not force:
            raise click.ClickException(
                "Refusing to seed demo accounts in production. "
                "Use --force to override."
            )

        try:
            result = seed_demo(app.config["DEMO_PASSWORD"])
        except (ApiError, ValueError) as exc:
            message = exc.message if isinstance(exc, ApiError) else str(exc)
            raise click.ClickException(message) from exc

        click.echo(
            f"Demo accounts: {result['users_created']} created, "
            f"{result['users_skipped']} skipped."
        )
        click.echo(
            "Demo tenant: "
            f"organization {'created' if result['tenant_created'] else 'existing'}, "
            f"workspace {'created' if result['workspace_created'] else 'existing'}, "
            f"project {'created' if result['project_created'] else 'existing'}, "
            f"{result['tasks_created']} tasks and "
            f"{result['dependencies_created']} dependencies created."
        )
