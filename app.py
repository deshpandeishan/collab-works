from flask import Flask, render_template, redirect, request, flash, jsonify, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from flask_bcrypt import Bcrypt
from urllib.parse import urlparse, urljoin
import requests
import json
import os
from datetime import datetime

app = Flask(__name__)

# ============================
# API: Role Prediction Handling
# ============================

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

        # Clear roles file after reading
        with open(roles_file, "w") as f:
            json.dump([], f)

        return jsonify(roles_data)
    return jsonify({"error": "roles.json not found"}), 404


# ============================
# Base Routes
# ============================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/header')
def header():
    return render_template('header.html')

@app.route('/footer')
def footer():
    return render_template('footer.html')


# ============================
# Client Account System
# ============================

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'thisisasecretkey'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager(app)
login_manager.login_view = 'client_login'

@login_manager.user_loader
def load_client(client_id):
    return Client.query.get(int(client_id))


# Client Database Model
class Client(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    email = db.Column(db.String(120), nullable=True, unique=True)
    first_name = db.Column(db.String(20), nullable=True)
    password = db.Column(db.String(80), nullable=False)


# Client Registration Form
class ClientRegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": " "})
    email = StringField(validators=[Length(max=120)], render_kw={"placeholder": " "})
    first_name = StringField(validators=[Length(max=20)], render_kw={"placeholder": " "})
    password = PasswordField(validators=[InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": " "})
    submit = SubmitField('Register')

    def validate_username(self, username):
        existing_client = Client.query.filter_by(username=username.data).first()
        if existing_client:
            raise ValidationError('That username already exists. Please choose a different one.')

    def validate_email(self, email):
        existing_client = Client.query.filter_by(email=email.data).first()
        if existing_client:
            raise ValidationError('This email is already registered. Try logging in instead.')


# Client Login Form
class ClientLoginForm(FlaskForm):
    email = StringField(validators=[InputRequired()], render_kw={"placeholder": "Email"})
    password = PasswordField(validators=[InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "Password"})
    submit = SubmitField('Login')


# ============================
# Client Auth Utilities
# ============================

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


# ============================
# Client Auth Routes
# ============================

@app.route('/client/login', methods=['GET', 'POST'])
def client_login():
    if current_user.is_authenticated:
        next_page = request.args.get('next')
        if next_page and is_safe_url(next_page):
            return redirect(next_page)
        return redirect(url_for('index'))

    form = ClientLoginForm()
    if form.validate_on_submit():
        client = Client.query.filter_by(email=form.email.data).first()

        if client and bcrypt.check_password_hash(client.password, form.password.data):
            login_user(client)
            next_page = request.args.get('next')
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Login unsuccessful. Please check your email and password.', 'danger')
    else:
        if request.method == 'POST':
            print("Form submission failed:", form.errors)

    return render_template('auth/client_login.html', form=form)


@app.route('/client/logout', methods=['GET', 'POST'])
@login_required
def client_logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/client/register', methods=['GET', 'POST'])
def client_register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = ClientRegisterForm()
    if form.validate_on_submit():
        existing_client = Client.query.filter_by(email=form.email.data).first()
        if existing_client:
            flash('This email is already registered. Try logging in instead.', 'danger')
            return render_template('auth/client_register.html', form=form)
        
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        new_client = Client(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            password=hashed_password
        )
        
        db.session.add(new_client)
        db.session.commit()
        flash('Client account created successfully! You can now log in.', 'success')
        return redirect(url_for('client_login'))
    return render_template('auth/client_register.html', form=form)


@app.route('/client/delete-account', methods=['POST'])
@login_required
def client_delete_account():
    try:
        client_id = current_user.id
        Client.query.filter_by(id=client_id).delete()
        db.session.commit()
        logout_user()
        return jsonify({"message": "Account deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/client/check_username', methods=['GET'])
def check_client_username():
    username = request.args.get('username')
    existing_client = Client.query.filter_by(username=username).first()
    return jsonify({'available': not bool(existing_client)})


@app.route('/client/check_email', methods=['GET'])
def check_client_email():
    email = request.args.get('email')
    if email:
        email_exists = Client.query.filter_by(email=email).first() is not None
        return jsonify({'exists': email_exists})
    return jsonify({'exists': False})


# ============================
# Static Policy Pages
# ============================

@app.route('/terms-of-service')
def terms_of_service():
    return render_template('terms_of_service.html')

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')


# ============================
# Main Entrypoint
# ============================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8000, debug=True)
