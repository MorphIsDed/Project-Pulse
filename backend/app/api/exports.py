from flask import Blueprint, Response
from flask_login import current_user, login_required

from app.services.export import project_ics
from app.services.tenancy import require_project_membership


exports_api = Blueprint("exports_api", __name__, url_prefix="/api/v1")


@exports_api.get("/projects/<int:project_id>/export.ics")
@login_required
def export_project_ics(project_id):
    project, _membership = require_project_membership(
        project_id, current_user.id
    )
    filename = "".join(
        character
        if character.isalnum() or character in {"-", "_"}
        else "-"
        for character in project.name
    ).strip("-") or "project"
    return Response(
        project_ics(project),
        mimetype="text/calendar",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}.ics"'
            ),
            "Cache-Control": "no-store",
        },
    )
