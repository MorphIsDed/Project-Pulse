from flask import Blueprint,jsonify,request,session
from app import get_db

notifications_api=Blueprint("notifications_api",__name__)

@notifications_api.get("/api/v1/notifications")
def list_notifications():
    uid=session.get("user_id")
    if not uid:return jsonify(error={"code":"not_authenticated","message":"Please log in."}),401
    rows=get_db().execute("SELECT id,organization_id,project_id,task_id,kind,message,read_at,created_at FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 100",(uid,)).fetchall();return jsonify(notifications=[dict(r) for r in rows])

@notifications_api.patch("/api/v1/notifications/<int:notification_id>")
def mark_read(notification_id):
    uid=session.get("user_id")
    if not uid:return jsonify(error={"code":"not_authenticated","message":"Please log in."}),401
    db=get_db();cur=db.execute("UPDATE notifications SET read_at=COALESCE(read_at,CURRENT_TIMESTAMP) WHERE id=? AND user_id=?",(notification_id,uid));db.commit()
    if not cur.rowcount:return jsonify(error={"code":"not_found","message":"Notification not found."}),404
    return jsonify(message="Notification marked as read.")
