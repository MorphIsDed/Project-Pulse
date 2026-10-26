import json
import secrets
from flask import Blueprint, jsonify, request, session, Response
from werkzeug.security import check_password_hash
from app import get_db
from app.security import token_hash

accounts_api=Blueprint("accounts_api",__name__)

TABLES=("organizations","organization_memberships","workspaces","projects","tasks","dependencies","resources","assignments","analysis_runs","audit_events","calendars")

@accounts_api.get("/api/v1/account/export")
def export_account():
    uid=session.get("user_id")
    if not uid:return jsonify(error={"code":"not_authenticated","message":"Please log in."}),401
    db=get_db(); org_ids=[r[0] for r in db.execute("SELECT organization_id FROM organization_memberships WHERE user_id=?",(uid,)).fetchall()]
    result={"export_version":1,"user":dict(db.execute("SELECT id,email,display_name,email_verified_at,created_at FROM users WHERE id=?",(uid,)).fetchone()),"organizations":[]}
    for oid in org_ids:
        org=dict(db.execute("SELECT * FROM organizations WHERE id=?",(oid,)).fetchone()); org["memberships"]=[dict(r) for r in db.execute("SELECT organization_id,user_id,role,created_at FROM organization_memberships WHERE organization_id=?",(oid,)).fetchall()]; org["audit_events"]=[dict(r) for r in db.execute("SELECT * FROM audit_events WHERE organization_id=?",(oid,)).fetchall()]
        org["workspaces"]=[]
        for w in db.execute("SELECT * FROM workspaces WHERE organization_id=?",(oid,)).fetchall():
            workspace=dict(w); workspace["projects"]=[]
            for p in db.execute("SELECT * FROM projects WHERE workspace_id=?",(w["id"],)).fetchall():
                project=dict(p)
                for table in ("tasks","dependencies","resources","analysis_runs","calendars"):
                    project[table]=[dict(r) for r in db.execute(f"SELECT * FROM {table} WHERE project_id=?",(p["id"],)).fetchall()]
                task_ids=[t["id"] for t in project["tasks"]]
                project["assignments"]=[dict(r) for r in db.execute("SELECT a.* FROM assignments a JOIN tasks t ON t.id=a.task_id WHERE t.project_id=?",(p["id"],)).fetchall()]
                workspace["projects"].append(project)
            org["workspaces"].append(workspace)
        result["organizations"].append(org)
    return Response(json.dumps(result,indent=2,default=str),mimetype="application/json",headers={"Content-Disposition":"attachment; filename=projectpulse-account-export.json"})

@accounts_api.delete("/api/v1/account")
def delete_account():
    uid=session.get("user_id"); data=request.get_json(silent=True) or {}
    if not uid:return jsonify(error={"code":"not_authenticated","message":"Please log in."}),401
    db=get_db(); user=db.execute("SELECT password_hash FROM users WHERE id=?",(uid,)).fetchone()
    if not check_password_hash(user["password_hash"],data.get("password","")):return jsonify(error={"code":"invalid_credentials","message":"Password is incorrect."}),403
    db.execute("BEGIN IMMEDIATE")
    orgs=db.execute("SELECT organization_id FROM organization_memberships WHERE user_id=?",(uid,)).fetchall()
    for row in orgs:
        oid=row[0]; count=db.execute("SELECT COUNT(*) FROM organization_memberships WHERE organization_id=?",(oid,)).fetchone()[0]
        if count==1:db.execute("DELETE FROM organizations WHERE id=?",(oid,))
        else:
            owned=db.execute("SELECT role FROM organization_memberships WHERE organization_id=? AND user_id=?",(oid,uid)).fetchone()
            if owned and owned["role"]=="owner":
                successor=db.execute("SELECT user_id FROM organization_memberships WHERE organization_id=? AND user_id<>? ORDER BY CASE role WHEN 'admin' THEN 0 ELSE 1 END,created_at,user_id LIMIT 1",(oid,uid)).fetchone()
                if successor:db.execute("UPDATE organization_memberships SET role='owner' WHERE organization_id=? AND user_id=?",(oid,successor["user_id"]))
    db.execute("DELETE FROM users WHERE id=?",(uid,));db.commit();session.clear()
    return jsonify(message="Account and sole-member workspace data deleted. Shared workspace data remains available to its other members."),200

@accounts_api.get("/api/v1/workspaces/<int:workspace_id>/export")
def export_workspace(workspace_id):
    uid=session.get("user_id")
    if not uid:return jsonify(error={"code":"not_authenticated","message":"Please log in."}),401
    db=get_db(); row=db.execute("SELECT w.id,w.organization_id,w.name FROM workspaces w JOIN organization_memberships m ON m.organization_id=w.organization_id WHERE w.id=? AND m.user_id=?",(workspace_id,uid)).fetchone()
    if not row:return jsonify(error={"code":"not_found","message":"Workspace not found."}),404
    projects=[dict(p) for p in db.execute("SELECT * FROM projects WHERE workspace_id=?",(workspace_id,)).fetchall()]
    for p in projects:
        for table in ("tasks","dependencies","resources","analysis_runs","calendars"):
            p[table]=[dict(r) for r in db.execute(f"SELECT * FROM {table} WHERE project_id=?",(p["id"],)).fetchall()]
        p["assignments"]=[dict(r) for r in db.execute("SELECT a.* FROM assignments a JOIN tasks t ON t.id=a.task_id WHERE t.project_id=?",(p["id"],)).fetchall()]
    return jsonify(workspace=dict(row),projects=projects)

@accounts_api.delete("/api/v1/workspaces/<int:workspace_id>")
def delete_workspace(workspace_id):
    uid=session.get("user_id"); db=get_db()
    if not uid:return jsonify(error={"code":"not_authenticated","message":"Please log in."}),401
    row=db.execute("SELECT w.id FROM workspaces w JOIN organization_memberships m ON m.organization_id=w.organization_id WHERE w.id=? AND m.user_id=? AND m.role IN ('owner','admin')",(workspace_id,uid)).fetchone()
    if not row:return jsonify(error={"code":"not_found","message":"Workspace not found or admin role required."}),404
    db.execute("DELETE FROM workspaces WHERE id=?",(workspace_id,));db.commit();return jsonify(message="Workspace and its project data deleted."),200

@accounts_api.post("/api/v1/account/import-guest")
def import_guest():
    uid=session.get("user_id"); data=request.get_json(silent=True) or {}; draft=data.get("draft_id"); snapshot=data.get("snapshot")
    if not uid:return jsonify(error={"code":"not_authenticated","message":"Please log in."}),401
    if not isinstance(draft,str) or len(draft)>100 or not isinstance(snapshot,dict):return jsonify(error={"code":"invalid_guest_data","message":"Guest data is incomplete."}),400
    db=get_db(); db.execute("CREATE TABLE IF NOT EXISTS guest_imports(user_id INTEGER NOT NULL,draft_id TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(user_id,draft_id),FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)")
    if db.execute("SELECT 1 FROM guest_imports WHERE user_id=? AND draft_id=?",(uid,draft)).fetchone():return jsonify(imported=True,already_imported=True),200
    # Validate the entire payload before any insert; all writes share one transaction.
    organizations=snapshot.get("organizations",[]); workspaces=snapshot.get("workspaces",[]); projects=snapshot.get("projects",[]); tasks=snapshot.get("tasks",[])
    if not all(isinstance(v,list) for v in (organizations,workspaces,projects,tasks)) or len(organizations)>20 or len(workspaces)>100 or len(projects)>500 or len(tasks)>10000:return jsonify(error={"code":"invalid_guest_data","message":"Guest data exceeds supported limits."}),400
    try:
        db.execute("BEGIN IMMEDIATE"); orgmap={}; wsmap={}; pmap={}; tmap={}
        for o in organizations:
            cur=db.execute("INSERT INTO organizations(name) VALUES(?)",(str(o.get("name","My organization"))[:120],));orgmap[o.get("id")]=cur.lastrowid;db.execute("INSERT INTO organization_memberships(organization_id,user_id,role) VALUES(?,?,'owner')",(cur.lastrowid,uid))
        for w in workspaces:
            oid=orgmap.get(w.get("organization_id")) or next(iter(orgmap.values()),None)
            if oid is None:continue
            cur=db.execute("INSERT INTO workspaces(organization_id,name) VALUES(?,?)",(oid,str(w.get("name","My workspace"))[:120]));wsmap[w.get("id")]=cur.lastrowid
        for p in projects:
            wid=wsmap.get(p.get("workspace_id"))
            if not wid:continue
            cur=db.execute("INSERT INTO projects(workspace_id,name,status,start_date,target_finish,created_by) VALUES(?,?,?,?,?,?)",(wid,str(p.get("name","Untitled project"))[:120],p.get("status","active") if p.get("status") in ('active','on_hold','completed','archived') else 'active',p.get("start_date"),p.get("target_finish"),uid));pmap[p.get("id")]=cur.lastrowid
        for t in tasks:
            pid=pmap.get(t.get("project_id"))
            if not pid:continue
            cur=db.execute("INSERT INTO tasks(project_id,name,description,status,duration_work_minutes,progress,priority) VALUES(?,?,?,?,?,?,?)",(pid,str(t.get("name","Untitled task"))[:200],str(t.get("description",""))[:20000],t.get("status") if t.get("status") in ('not_started','in_progress','blocked','completed') else 'not_started',max(0,min(int(t.get("duration_work_minutes",0)),10000000)),max(0,min(int(t.get("progress",0)),100)),max(1,min(int(t.get("priority",3)),5))));tmap[t.get("id")]=cur.lastrowid
        db.execute("INSERT INTO guest_imports(user_id,draft_id) VALUES(?,?)",(uid,draft));db.commit()
    except Exception:
        db.rollback();return jsonify(error={"code":"guest_import_failed","message":"Guest data was not partially saved. It remains on this device; retry the save."}),400
    return jsonify(imported=True,already_imported=False),201
