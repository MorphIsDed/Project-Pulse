import secrets
from datetime import datetime,timedelta,timezone
from flask import Blueprint,jsonify,request,session,current_app
from app import get_db
from app.mail import send_email
from app.security import token_hash

invitations_api=Blueprint("invitations_api",__name__)

@invitations_api.post("/api/v1/organizations/<int:org_id>/invitations")
def invite(org_id):
    uid=session.get("user_id");data=request.get_json(silent=True) or {};email=str(data.get("email","")).strip().lower();role=data.get("role","member")
    if not uid:return jsonify(error={"code":"not_authenticated","message":"Please log in."}),401
    db=get_db();member=db.execute("SELECT role FROM organization_memberships WHERE organization_id=? AND user_id=?",(org_id,uid)).fetchone()
    if not member or member["role"] not in ("owner","admin"):return jsonify(error={"code":"forbidden","message":"Organization admin role required."}),403
    if "@" not in email or role not in ("admin","member"):return jsonify(error={"code":"invalid_invitation","message":"Enter a valid email and choose admin or member."}),400
    token=secrets.token_urlsafe(32);expires=(datetime.now(timezone.utc)+timedelta(days=7)).isoformat()
    db.execute("DELETE FROM workspace_invitations WHERE organization_id=? AND email=? COLLATE NOCASE AND accepted_at IS NULL",(org_id,email));db.execute("INSERT INTO workspace_invitations(organization_id,email,role,token_hash,invited_by,expires_at) VALUES(?,?,?,?,?,?)",(org_id,email,role,token_hash(token),uid,expires));db.commit()
    try:send_email(email,"ProjectPulse workspace invitation",f"You have been invited to join a ProjectPulse organization as {role}. Sign in or create your account, then open this link to accept:\n\n{current_app.config['PUBLIC_URL']}/?invite_token={token}\n\nThe invitation expires in 7 days.")
    except Exception:current_app.logger.exception("Invitation delivery failed");return jsonify(error={"code":"email_delivery_failed","message":"Invitation saved, but the email could not be delivered. Please retry after checking mail settings."}),503
    return jsonify(message="Invitation sent."),201

@invitations_api.get("/api/v1/organizations/<int:org_id>/invitations")
def list_invitations(org_id):
    uid=session.get("user_id");db=get_db()
    row=db.execute("SELECT role FROM organization_memberships WHERE organization_id=? AND user_id=?",(org_id,uid)).fetchone() if uid else None
    if not row or row["role"] not in ("owner","admin"):return jsonify(error={"code":"forbidden","message":"Organization admin role required."}),403
    items=db.execute("SELECT id,email,role,expires_at,created_at FROM workspace_invitations WHERE organization_id=? AND accepted_at IS NULL ORDER BY created_at DESC",(org_id,)).fetchall();return jsonify(invitations=[dict(x) for x in items])

@invitations_api.delete("/api/v1/organizations/<int:org_id>/invitations/<int:invitation_id>")
def revoke(org_id,invitation_id):
    uid=session.get("user_id");db=get_db();row=db.execute("SELECT role FROM organization_memberships WHERE organization_id=? AND user_id=?",(org_id,uid)).fetchone() if uid else None
    if not row or row["role"] not in ("owner","admin"):return jsonify(error={"code":"forbidden","message":"Organization admin role required."}),403
    db.execute("DELETE FROM workspace_invitations WHERE id=? AND organization_id=?",(invitation_id,org_id));db.commit();return "",204

@invitations_api.post("/api/v1/invitations/accept")
def accept():
    uid=session.get("user_id");token=(request.get_json(silent=True) or {}).get("token","")
    if not uid:return jsonify(error={"code":"not_authenticated","message":"Sign in to accept the invitation."}),401
    db=get_db();row=db.execute("SELECT i.*,u.email FROM workspace_invitations i JOIN users u ON u.id=? WHERE i.token_hash=? AND i.accepted_at IS NULL",(uid,token_hash(token))).fetchone()
    if not row or row["expires_at"]<datetime.now(timezone.utc).isoformat():return jsonify(error={"code":"invalid_invitation","message":"This invitation is invalid or expired."}),400
    user=db.execute("SELECT email,email_verified_at FROM users WHERE id=?",(uid,)).fetchone()
    if user["email"].lower()!=row["email"].lower():return jsonify(error={"code":"invitation_email_mismatch","message":"Sign in with the invited email address."}),403
    if not user["email_verified_at"]:return jsonify(error={"code":"email_verification_required","message":"Verify your email before accepting."}),403
    db.execute("INSERT INTO organization_memberships(organization_id,user_id,role) VALUES(?,?,?) ON CONFLICT(organization_id,user_id) DO UPDATE SET role=excluded.role",(row["organization_id"],uid,row["role"]));db.execute("UPDATE workspace_invitations SET accepted_at=CURRENT_TIMESTAMP WHERE id=?",(row["id"],));db.commit();return jsonify(message="Invitation accepted.",organization_id=row["organization_id"]),200
