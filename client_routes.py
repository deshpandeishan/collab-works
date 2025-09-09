from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user, UserMixin
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from urllib.parse import urlparse, urljoin
import uuid
from extensions import db, bcrypt

client_bp = Blueprint('client', __name__)

class Client(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    unique_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(120), nullable=True, unique=True)
    first_name = db.Column(db.String(20), nullable=True)
    password = db.Column(db.String(80), nullable=False)

    @property
    def role(self):
        return "client"

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

class ClientLoginForm(FlaskForm):
    email = StringField(validators=[InputRequired()], render_kw={"placeholder": "Email"})
    password = PasswordField(validators=[InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "Password"})
    submit = SubmitField('Login')

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

@client_bp.route('/login', methods=['GET', 'POST'])
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

    return render_template('auth/client_login.html', form=form)

@client_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def client_logout():
    logout_user()
    return redirect(url_for('index'))

@client_bp.route('/register', methods=['GET', 'POST'])
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
    return render_template('auth/client_register.html', form=form)

@client_bp.route('/delete-account', methods=['POST'])
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

@client_bp.route('/check_username', methods=['GET'])
def check_client_username():
    username = request.args.get('username')
    existing_client = Client.query.filter_by(username=username).first()
    return jsonify({'available': not bool(existing_client)})

@client_bp.route('/check_email', methods=['GET'])
def check_client_email():
    email = request.args.get('email')
    if email:
        email_exists = Client.query.filter_by(email=email).first() is not None
        return jsonify({'exists': email_exists})
    return jsonify({'exists': False})
