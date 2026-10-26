import json
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from flask import Blueprint,jsonify,request,session
from app import get_db

calendars_api=Blueprint("calendars_api",__name__)

def project_access(project_id,uid):
    return get_db().execute("SELECT p.id,p.calendar_id FROM projects p JOIN workspaces w ON w.id=p.workspace_id JOIN organization_memberships m ON m.organization_id=w.organization_id WHERE p.id=? AND m.user_id=?",(project_id,uid)).fetchone()

@calendars_api.get("/api/v1/projects/<int:project_id>/calendar")
def get_calendar(project_id):
    uid=session.get("user_id")
    if not uid:return jsonify(error={"code":"not_authenticated","message":"Please log in."}),401
    p=project_access(project_id,uid)
    if not p:return jsonify(error={"code":"not_found","message":"Project not found."}),404
    row=get_db().execute("SELECT * FROM calendars WHERE project_id=?",(project_id,)).fetchone()
    return jsonify(calendar={"timezone":"UTC","working_days":[0,1,2,3,4],"holidays":[]} if not row else {"id":row["id"],"name":row["name"],"timezone":row["timezone"],"weekly_rules":json.loads(row["weekly_rules"]),"exceptions":json.loads(row["exceptions"])}),200

@calendars_api.put("/api/v1/projects/<int:project_id>/calendar")
def update_calendar(project_id):
    uid=session.get("user_id");data=request.get_json(silent=True) or {}
    if not uid:return jsonify(error={"code":"not_authenticated","message":"Please log in."}),401
    p=project_access(project_id,uid)
    if not p:return jsonify(error={"code":"not_found","message":"Project not found."}),404
    role=get_db().execute("SELECT m.role FROM projects p JOIN workspaces w ON w.id=p.workspace_id JOIN organization_memberships m ON m.organization_id=w.organization_id WHERE p.id=? AND m.user_id=?",(project_id,uid)).fetchone()["role"]
    if role not in ("owner","admin"):return jsonify(error={"code":"forbidden","message":"Workspace admin role required."}),403
    tz=data.get("timezone","UTC");days=data.get("working_days",[0,1,2,3,4]);holidays=data.get("holidays",[])
    try:ZoneInfo(tz)
    except (ZoneInfoNotFoundError,TypeError):return jsonify(error={"code":"invalid_timezone","message":"Choose a valid time zone."}),400
    if not isinstance(days,list) or any(type(x) is not int or x not in range(7) for x in days) or len(set(days))!=len(days) or not days:return jsonify(error={"code":"invalid_workdays","message":"Choose one or more unique weekdays (0=Monday)."}),400
    if not isinstance(holidays,list) or len(holidays)>500:return jsonify(error={"code":"invalid_holidays","message":"Holidays must be a list of up to 500 ISO dates."}),400
    try:
        from datetime import date
        for holiday in holidays:date.fromisoformat(holiday)
    except (ValueError,TypeError):return jsonify(error={"code":"invalid_holidays","message":"Use YYYY-MM-DD for each holiday."}),400
    db=get_db();db.execute("INSERT INTO calendars(project_id,name,timezone,weekly_rules,exceptions) VALUES(?,?,?,?,?) ON CONFLICT(project_id) DO UPDATE SET timezone=excluded.timezone,weekly_rules=excluded.weekly_rules,exceptions=excluded.exceptions,updated_at=CURRENT_TIMESTAMP",(project_id,"Project calendar",tz,json.dumps({"working_days":days}),json.dumps({"holidays":holidays})));db.execute("UPDATE projects SET version=version+1 WHERE id=?",(project_id,));db.commit()
    return jsonify(message="Calendar settings saved."),200
