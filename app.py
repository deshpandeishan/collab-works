from flask import Flask, render_template, jsonify, request
from flask_login import LoginManager
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

# url to fetch predicted roles for the need statement
AZURE_API_URL = "https://roles-predictor-bzg4fdfwgzb0hjh7.eastasia-01.azurewebsites.net/predict"

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
            "id": f.id,
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
