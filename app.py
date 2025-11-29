from flask import Flask, redirect, render_template, jsonify, request, url_for
from flask_login import LoginManager, current_user, login_required
from datetime import datetime
import requests, os, json
from extensions import db, bcrypt
from client_routes import client_bp, Client
from freelancer_routes import freelancer_bp, Freelancer
import joblib
import os, json, joblib
import sqlite3


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'b7c4f2e9a1dd4c0fb2e8a6d7c3f9b1a2'

db.init_app(app)
bcrypt.init_app(app)
login_manager = LoginManager(app)

app.register_blueprint(client_bp, url_prefix="/client")
app.register_blueprint(freelancer_bp, url_prefix="/freelancer")


@login_manager.user_loader
def load_user(user_id):
    user = db.session.get(Client, int(user_id))
    if not user:
        user = db.session.get(Freelancer, int(user_id))
    return user



class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conv_id = db.Column(db.Integer)
    user = db.Column(db.String(50))
    receiver_id = db.Column(db.String(36))
    from_me = db.Column(db.Boolean)
    text = db.Column(db.String(500))
    time = db.Column(db.String(20))


@app.route('/start_chat/<int:freelancer_id>')
@login_required
def start_chat(freelancer_id):
    if not isinstance(current_user, Client):
        return redirect(url_for('client_bp.login'))

    conv = (
        Message.query.filter_by(receiver_id=str(freelancer_id))
        .order_by(Message.conv_id.asc())
        .first()
    )
    if conv:
        conv_id = conv.conv_id
    else:
        max_conv = db.session.query(db.func.max(Message.conv_id)).scalar() or 0
        conv_id = max_conv + 1
        msg = Message(
            conv_id=conv_id,
            user=current_user.id,
            receiver_id=str(freelancer_id),
            from_me=True,
            text="Started a new conversation",
            time=datetime.now().strftime("%I:%M %p").lstrip("0"),
        )
        db.session.add(msg)
        db.session.commit()

    return redirect(url_for('chat_page', conv=conv_id, user=current_user.id))


@app.route("/chat_page")
@login_required
def chat_page():
    current_user_id = str(current_user.id)
    user_type = "freelancer" if isinstance(current_user, Freelancer) else "client"

    conv_ids = db.session.query(Message.conv_id).distinct().all()
    conversations = []

    for cid_tuple in conv_ids:
        cid = cid_tuple[0]
        msgs = Message.query.filter_by(conv_id=cid).all()
        if not msgs:
            continue

        other_user_id = None
        for m in msgs:
            if str(m.user) != current_user_id and m.user != "Server":
                other_user_id = m.user
                break
            elif str(m.receiver_id) != current_user_id and m.receiver_id != "Server":
                other_user_id = m.receiver_id
                break

        if user_type == "freelancer":
            other = Client.query.get(other_user_id)
        else:
            other = Freelancer.query.get(other_user_id)

        name = f"{getattr(other,'first_name','')} {getattr(other,'last_name','')}".strip() if other else f"Conversation {cid}"
        avatar = "/static/img/search/male-pfp.webp"
        last_msg = msgs[-1]

        conversations.append({
            "id": cid,
            "name": name,
            "avatar": avatar,
            "last_message": last_msg.text,
            "timestamp": last_msg.time,
            "unique_id": other_user_id,
            "messages": [
                {"text": m.text, "time": m.time, "from_me": m.user == current_user_id, "user": m.user}
                for m in msgs
            ]
        })

    active_conv_id = conversations[0]['id'] if conversations else 0

    template = "chat/freelancer_chat.html" if user_type == "freelancer" else "chat/client_chat.html"

    return render_template(template,
                           conversations=conversations,
                           active_id=active_conv_id,
                           user=current_user.id)


@app.route("/freelancer_chat")
@login_required
def freelancer_chat():
    if not isinstance(current_user, Freelancer):
        return redirect(url_for('freelancer_bp.login'))

    current_freelancer_id = str(current_user.id)
    conv_ids = db.session.query(Message.conv_id).distinct().all()
    conversations = []

    for cid_tuple in conv_ids:
        cid = cid_tuple[0]
        msgs = Message.query.filter_by(conv_id=cid).all()
        if not msgs:
            continue

        if not any(
            str(m.user) == current_freelancer_id or str(m.receiver_id) == current_freelancer_id
            for m in msgs
        ):
            continue

        client_id = None
        for m in msgs:
            if str(m.user) != current_freelancer_id and Client.query.get(int(m.user)):
                client_id = m.user
                break
            elif str(m.receiver_id) != current_freelancer_id and Client.query.get(int(m.receiver_id)):
                client_id = m.receiver_id
                break

        client = Client.query.get(int(client_id)) if client_id else None
        if not client:
            continue

        name = f"{client.first_name} {client.last_name}".strip() or f"Client {client_id}"
        avatar = "/static/img/search/male-pfp.webp"
        last_msg = msgs[-1]

        conversations.append({
            "id": cid,
            "name": name,
            "avatar": avatar,
            "last_message": last_msg.text,
            "timestamp": last_msg.time,
            "unique_id": client_id,
            "messages": [
                {
                    "text": m.text,
                    "time": m.time,
                    "from_me": str(m.user) == current_freelancer_id,
                    "user": m.user
                } for m in msgs
            ]
        })

    return render_template(
        "chat/freelancer_chat.html",
        conversations=conversations,
        active_id=conversations[0]['id'] if conversations else 0,
        user=current_user.id
    )



@app.route("/chat/<int:conv_id>")
@login_required
def get_conversation(conv_id):
    msgs = Message.query.filter_by(conv_id=conv_id).all()
    if not msgs:
        return jsonify({"error": "No messages found"}), 404

    current_user_id = str(current_user.id)
    other_id = None
    if isinstance(current_user, Freelancer):
        for m in msgs:
            if str(m.user) != current_user_id and Client.query.get(int(m.user)):
                other_id = m.user
                break
            elif str(m.receiver_id) != current_user_id and Client.query.get(int(m.receiver_id)):
                other_id = m.receiver_id
                break
        other_user = Client.query.get(int(other_id)) if other_id else None
    else:
        for m in msgs:
            if str(m.user) != current_user_id and Freelancer.query.get(int(m.user)):
                other_id = m.user
                break
            elif str(m.receiver_id) != current_user_id and Freelancer.query.get(int(m.receiver_id)):
                other_id = m.receiver_id
                break
        other_user = Freelancer.query.get(int(other_id)) if other_id else None

    name = f"{getattr(other_user,'first_name','')} {getattr(other_user,'last_name','')}".strip() if other_user else f"Conversation {conv_id}"
    avatar = "/static/img/search/male-pfp.webp"

    data = {
        "id": conv_id,
        "name": name,
        "avatar": avatar,
        "unique_id": other_id,
        "messages": [
            {
                "text": m.text,
                "time": m.time,
                "from_me": str(m.user) == current_user_id,
                "user": m.user
            } for m in msgs
        ]
    }
    return jsonify(data)




@app.route("/send", methods=["POST"])
@login_required
def send():
    data = request.json
    conv_id = int(data.get("conv_id"))
    text = data.get("text", "").strip()
    user = data.get("user", current_user.id)
    receiver_id = data.get("receiver_id")

    if not text or not receiver_id:
        return jsonify({"error": "empty or missing receiver"}), 400

    now = datetime.now().strftime("%I:%M %p").lstrip("0")
    msg = Message(conv_id=conv_id, user=user, receiver_id=receiver_id, from_me=True, text=text, time=now)
    db.session.add(msg)
    db.session.commit()

    return jsonify({"status": "ok", "message": {"from_me": True, "text": text, "time": now}})


@app.route("/receive/<int:conv_id>")
@login_required
def receive(conv_id):
    now = datetime.now().strftime("%I:%M %p").lstrip("0")
    reply = Message(conv_id=conv_id, user="Server", from_me=False, text="Got your message!", time=now)
    db.session.add(reply)
    db.session.commit()
    return jsonify({"status": "ok", "message": {"from_me": False, "text": reply.text, "time": now}})


clf = joblib.load("role_predictor_new.pkl")
mlb = joblib.load("mlb_new.pkl")
thresholds = joblib.load("thresholds_new.pkl")

def predict_roles_local(text, top_n=3):
    probas = clf.predict_proba([text])[0]
    preds = []
    for i, p in enumerate(probas):
        if p >= thresholds[i]:
            preds.append((mlb.classes_[i], p))
    preds.sort(key=lambda x: x[1], reverse=True)
    return [role for role, _ in preds[:top_n]]

@app.route('/predict_roles', methods=['POST'])
def predict_roles():
    need_statement = request.form.get("need_statement")
    top_n = int(request.form.get("top_n", 4))

    try:
        predicted_roles = predict_roles_local(need_statement, top_n)
        generic_roles = {"Developer", "Engineer", "Designer"}
        if not predicted_roles or all(role in generic_roles for role in predicted_roles):
            friendly_message = (
                "Hmm, we couldn’t confidently match your request. "
                "Try rephrasing it with more details like the task or domain."
            )
            return jsonify({
                "need_statement": need_statement,
                "predicted_roles": [],
                "message": friendly_message
            })

        roles_file = "roles.json"
        roles_data = []
        if os.path.exists(roles_file):
            with open(roles_file, "r") as f:
                try:
                    roles_data = json.load(f)
                except json.JSONDecodeError:
                    roles_data = []

        entry = {
            "timestamp": datetime.now().isoformat(),
            "need_statement": need_statement,
            "roles": predicted_roles
        }
        roles_data.append(entry)
        with open(roles_file, "w") as f:
            json.dump(roles_data, f, indent=2)

        return jsonify({
            "need_statement": need_statement,
            "predicted_roles": predicted_roles
        })

    except Exception as e:
        return jsonify({
            "error": "Something went wrong while processing your request. Please try again."
        }), 500



@app.route("/get_roles", methods=["GET"])
def get_roles():
    roles_file = "roles.json"
    if os.path.exists(roles_file):
        with open(roles_file, "r") as f:
            roles_data = json.load(f)
        with open(roles_file, "w") as f:
            json.dump([], f)
        return jsonify(roles_data)
    return jsonify({"error": "roles.json not found"}), 404


import random

@app.route("/get_freelancers", methods=["GET"])
def get_freelancers():
    male_images = [
        "/static/img/search/male-1.webp",
        "/static/img/search/male-2.webp",
        "/static/img/search/male-3.webp",
        "/static/img/search/male-4.webp"
    ]

    female_images = [
        "/static/img/search/female-1.webp",
        "/static/img/search/female-2.webp",
        "/static/img/search/female-3.webp",
        "/static/img/search/female-4.webp"
    ]

    freelancers = Freelancer.query.all()
    result = []

    for f in freelancers:
        image = random.choice(
            female_images if f.gender.lower() == "female" else male_images
        )

        result.append({
            "unique_id": f.id,
            "name": f"{f.first_name} {f.last_name}".strip(),
            "username": f.username,
            "role": "Developer",
            "tagline": f.tagline,
            "location": f.location,
            "image": image,
            "rate": f"₹{(50 + f.id*10)}/hr",
            "rating": round(3.5 + (f.id % 15)/10, 1),
            "ratingCount": 20 + f.id*5,
            "ratingIcon": "/static/img/search/rating-icon.webp"
        })

    return jsonify(result)



@app.route("/check_client_status", methods=["GET"])
def check_client_status():
    if current_user.is_authenticated and isinstance(current_user, Client):
        return jsonify({"status": "ok"})
    return jsonify({"status": "unauthorized"})


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/header')
def header():
    return render_template('header.html')


@app.route('/footer')
def footer():
    return render_template('footer.html')


@app.route('/terms-of-service')
def terms_of_service():
    return render_template('docs/terms_of_service.html')


@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/freelancer')
def freelancer_dashboard():
    email = current_user.email

    conn = sqlite3.connect('instance/database.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT first_name, last_name, email, tagline, location, roles 
        FROM freelancer 
        WHERE email = ?
    """, (email,))
    row = cursor.fetchone()
    conn.close()

    if row:
        freelancer = {
            "name": f"{row[0]} {row[1]}" if row[1] else row[0],
            "email": row[2],
            "tagline": row[3],
            "location": row[4],
            "roles": row[5]
        }
    else:
        freelancer = None

    return render_template('freelancer/freelancer.html', freelancer=freelancer)



if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8000, debug=True)
