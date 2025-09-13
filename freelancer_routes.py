from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user, UserMixin
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from urllib.parse import urlparse, urljoin

from extensions import db, bcrypt

freelancer_bp = Blueprint('freelancer', __name__)

class Freelancer(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=True)
    password = db.Column(db.String(200), nullable=False)
    tagline = db.Column(db.String(200))
    location = db.Column(db.String(100))
    roles = db.Column(db.String(500))

    @property
    def role(self):
        return "freelancer"

class FreelancerRegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": " "})
    email = StringField(validators=[Length(max=120)], render_kw={"placeholder": " "})
    first_name = StringField(validators=[Length(max=20)], render_kw={"placeholder": " "})
    last_name = StringField(validators=[Length(max=20)], render_kw={"placeholder": " "})
    password = PasswordField(validators=[InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": " "})
    submit = SubmitField('Register')

    def validate_username(self, username):
        existing_freelancer = Freelancer.query.filter_by(username=username.data).first()
        if existing_freelancer:
            raise ValidationError('That username already exists. Please choose a different one.')

    def validate_email(self, email):
        existing_freelancer = Freelancer.query.filter_by(email=email.data).first()
        if existing_freelancer:
            raise ValidationError('This email is already registered. Try logging in instead.')

class FreelancerLoginForm(FlaskForm):
    email = StringField(validators=[InputRequired()], render_kw={"placeholder": "Email"})
    password = PasswordField(validators=[InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "Password"})
    submit = SubmitField('Login')

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

@freelancer_bp.route('/login', methods=['GET', 'POST'])
def freelancer_login():
    if current_user.is_authenticated:
        next_page = request.args.get('next')
        if next_page and is_safe_url(next_page):
            return redirect(next_page)
        return redirect(url_for('index'))

    form = FreelancerLoginForm()
    if form.validate_on_submit():
        freelancer = Freelancer.query.filter_by(email=form.email.data).first()
        if freelancer and bcrypt.check_password_hash(freelancer.password, form.password.data):
            login_user(freelancer)
            next_page = request.args.get('next')
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Login unsuccessful. Please check your email and password.', 'danger')

    return render_template('auth/freelancer_login.html', form=form)

@freelancer_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def freelancer_logout():
    logout_user()
    return redirect(url_for('index'))

@freelancer_bp.route('/register', methods=['GET', 'POST'])
def freelancer_register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = FreelancerRegisterForm()
    if form.validate_on_submit():
        existing_freelancer = Freelancer.query.filter_by(email=form.email.data).first()
        if existing_freelancer:
            flash('This email is already registered. Try logging in instead.', 'danger')
            return render_template('auth/freelancer_register.html', form=form)

        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        roles = request.form.get('roles')
        new_freelancer = Freelancer(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            password=hashed_password,
            roles=roles
        )

        db.session.add(new_freelancer)
        db.session.commit()
        flash('Freelancer account created successfully! You can now log in.', 'success')
        if current_user.is_authenticated:
            next_page = request.args.get('next')
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for('index'))

        form = FreelancerLoginForm()
        if form.validate_on_submit():
            freelancer = Freelancer.query.filter_by(email=form.email.data).first()
            if freelancer and bcrypt.check_password_hash(freelancer.password, form.password.data):
                login_user(freelancer)
                next_page = request.args.get('next')
                if next_page and is_safe_url(next_page):
                    return redirect(next_page)
                return redirect(url_for('index'))
            else:
                flash('Login unsuccessful. Please check your email and password.', 'danger')
            return redirect(url_for('index'))
    return render_template('auth/freelancer_register.html', form=form)


@freelancer_bp.route('/delete-account', methods=['POST'])
@login_required
def freelancer_delete_account():
    try:
        freelancer_id = current_user.id
        Freelancer.query.filter_by(id=freelancer_id).delete()
        db.session.commit()
        logout_user()
        return jsonify({"message": "Account deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@freelancer_bp.route('/check_username', methods=['GET'])
def check_freelancer_username():
    username = request.args.get('username')
    existing_freelancer = Freelancer.query.filter_by(username=username).first()
    return jsonify({'available': not bool(existing_freelancer)})

@freelancer_bp.route('/check_email', methods=['GET'])
def check_freelancer_email():
    email = request.args.get('email')
    if email:
        email_exists = Freelancer.query.filter_by(email=email).first() is not None
        return jsonify({'exists': email_exists})
    return jsonify({'exists': False})
