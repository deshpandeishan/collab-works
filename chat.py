from flask import Flask, render_template, jsonify, request
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
db = SQLAlchemy(app)
app.secret_key = 'jdk3j4h5k23j4h5k23j4h5k23j4h5'


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conv_id = db.Column(db.Integer)
    user = db.Column(db.String(50))
    receiver_id = db.Column(db.String(36))
    from_me = db.Column(db.Boolean)
    text = db.Column(db.String(500))
    time = db.Column(db.String(20))


with app.app_context():
    db.create_all()


@app.route("/chat")
def chat_page():
    user = request.args.get("user", "Guest")
    active_conv = int(request.args.get("conv", 1))

    conv_ids = db.session.query(Message.conv_id).distinct().all()
    conversations = []
    for cid_tuple in conv_ids:
        cid = cid_tuple[0]
        last_msg = (
            Message.query.filter_by(conv_id=cid)
            .order_by(Message.id.desc())
            .first()
        )
        if last_msg:
            conversations.append({
                "id": cid,
                "name": last_msg.user if last_msg.user != user else f"Conversation {cid}",
                "avatar": "/static/img/default.png",
                "last_message": last_msg.text,
                "timestamp": last_msg.time,
                "last_seen": "",
                "unique_id": last_msg.receiver_id,
                "messages": Message.query.filter_by(conv_id=cid).all()
            })

    return render_template(
        "chat/chat.html",
        conversations=conversations,
        active_id=active_conv,
        user=user
    )


@app.route("/chat/<int:conv_id>")
def chat(conv_id):
    msgs = Message.query.filter_by(conv_id=conv_id).all()
    if not msgs:
        return jsonify({"error": "not found"}), 404

    first_msg = msgs[0]
    conv_data = {
        "id": conv_id,
        "name": first_msg.user,
        "avatar": "/static/img/default.png",
        "last_seen": "",
        "messages": [
            {"from_me": m.from_me, "text": m.text, "time": m.time, "user": m.user}
            for m in msgs
        ]
    }
    return jsonify(conv_data)


@app.route("/send", methods=["POST"])
def send():
    data = request.json
    conv_id = int(data.get("conv_id"))
    text = data.get("text", "").strip()
    user = data.get("user", "Guest")
    receiver_id = data.get("receiver_id")

    if not text or not receiver_id:
        return jsonify({"error": "empty or missing receiver"}), 400

    now = datetime.now().strftime("%I:%M %p").lstrip("0")
    msg = Message(conv_id=conv_id, user=user, receiver_id=receiver_id, from_me=True, text=text, time=now)
    db.session.add(msg)
    db.session.commit()

    return jsonify({"status": "ok", "message": {"from_me": True, "text": text, "time": now}})


@app.route("/receive/<int:conv_id>")
def receive(conv_id):
    now = datetime.now().strftime("%I:%M %p").lstrip("0")
    reply = Message(conv_id=conv_id, user="Server", from_me=False, text="Got your message!", time=now)
    db.session.add(reply)
    db.session.commit()

    return jsonify({"status": "ok", "message": {"from_me": False, "text": reply.text, "time": now}})


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True)
