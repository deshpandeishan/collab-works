from flask import Flask, redirect, render_template, jsonify, request, url_for
from flask_login import LoginManager, current_user, login_required
from datetime import datetime
import requests, os, json
from extensions import db, bcrypt
from client_routes import client_bp, Client
from freelancer_routes import freelancer_bp, Freelancer


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'thisisasecretkey'

db.init_app(app)
bcrypt.init_app(app)
login_manager = LoginManager(app)

app.register_blueprint(client_bp, url_prefix="/client")
app.register_blueprint(freelancer_bp, url_prefix="/freelancer")


@login_manager.user_loader
def load_user(user_id):
    user = Client.query.get(int(user_id))
    if not user:
        user = Freelancer.query.get(int(user_id))
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
    user = request.args.get("user", current_user.id)
    active_conv = int(request.args.get("conv", 1))

    conv_ids = db.session.query(Message.conv_id).distinct().all()
    conversations = []

    for cid_tuple in conv_ids:
        cid = cid_tuple[0]
        msgs = Message.query.filter_by(conv_id=cid).all()
        if not msgs:
            continue

        freelancer_user_id = None
        if isinstance(current_user, Client):
            for m in msgs:
                if str(m.user) != str(current_user.id):
                    freelancer_user_id = m.user
                    break
                elif str(m.receiver_id) != str(current_user.id):
                    freelancer_user_id = m.receiver_id
                    break

        other = Freelancer.query.get(freelancer_user_id) or Client.query.get(freelancer_user_id)
        name = f"{getattr(other,'first_name','')} {getattr(other,'last_name','')}".strip() if other else f"Conversation {cid}"
        avatar = "/static/img/search/male-pfp.webp"

        last_msg = msgs[-1]

        conversations.append({
            "id": cid,
            "name": name,
            "avatar": avatar,
            "last_message": last_msg.text,
            "timestamp": last_msg.time,
            # "last_seen": "online",
            "unique_id": freelancer_user_id,
            "messages": [
                {"text": m.text, "time": m.time, "from_me": m.from_me, "user": m.user}
                for m in msgs
            ]
        })

    return render_template(
        "chat/client_chat.html",
        conversations=conversations,
        active_id=active_conv,
        user=user
    )

@app.route("/freelancer_chat")
@login_required
def freelancer_chat():
    # Ensure only freelancers can access
    if not isinstance(current_user, Freelancer):
        return redirect(url_for('freelancer_bp.login'))

    conv_ids = db.session.query(Message.conv_id).distinct().all()
    conversations = []
    for cid_tuple in conv_ids:
        cid = cid_tuple[0]
        msgs = Message.query.filter_by(conv_id=cid).all()
        if not msgs:
            continue

        # Identify client on the other side
        client_id = None
        for m in msgs:
            if str(m.user) != str(current_user.id) and m.user != "Server":
                client_id = m.user
                break
            elif str(m.receiver_id) != str(current_user.id):
                client_id = m.receiver_id
                break

        client = Client.query.get(client_id) if client_id else None
        name = f"{client.first_name} {client.last_name}" if client else f"Conversation {cid}"
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
                {"text": m.text, "time": m.time, "from_me": m.user == str(current_user.id), "user": m.user}
                for m in msgs
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
    for m in msgs:
        if str(m.user) != current_user_id:
            other_id = m.user
            break
        elif str(m.receiver_id) != current_user_id:
            other_id = m.receiver_id
            break

    # Try to find the other participant first as Freelancer, then as Client
    other_user = Freelancer.query.get(other_id)
    if not other_user:
        other_user = Client.query.get(other_id)

    if other_user:
        name = f"{getattr(other_user,'first_name','')} {getattr(other_user,'last_name','')}".strip()
    else:
        name = f"Conversation {conv_id}"

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


AZURE_API_URL = "https://npl-model-test-1.onrender.com/predict"

@app.route('/predict_roles', methods=['POST'])
def predict_roles():
    need_statement = request.form.get("need_statement")
    top_n = int(request.form.get("top_n", 3))
    try:
        response = requests.post(
            AZURE_API_URL,
            json={"need_statement": need_statement, "top_n": top_n},
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 200:
            result = response.json()
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
                "need_statement": result["need_statement"],
                "roles": result["predicted_roles"]
            }
            roles_data.append(entry)
            with open(roles_file, "w") as f:
                json.dump(roles_data, f, indent=2)
            return jsonify(result)
        else:
            return jsonify({"error": "Error fetching predictions from Azure API"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


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


@app.route("/get_freelancers", methods=["GET"])
def get_freelancers():
    freelancers = Freelancer.query.all()
    result = []
    for f in freelancers:
        result.append({
            "unique_id": f.id,
            "name": f"{f.first_name} {f.last_name}".strip(),
            "username": f.username,
            "role": "Developer",
            "tagline": f.tagline,
            "location": f.location,
            "image": "/static/img/search/male-pfp.webp" if f.username[-1] not in "aeiou" else "/static/img/search/female-pfp.webp",
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
    return render_template('terms_of_service.html')


@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8000, debug=True)
