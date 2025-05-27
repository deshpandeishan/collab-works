from flask import Flask, render_template, redirect, request, flash, jsonify, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from flask_bcrypt import Bcrypt
from urllib.parse import urlparse, urljoin
from flask_login import login_user, login_required, logout_user, current_user
from flask import Flask, render_template, redirect, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user


app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/header')
def header():
    return render_template('header.html')

@app.route('/footer')
def footer():
    return render_template('footer.html')

### Code for the account creation and login system ###
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'thisisasecretkey'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager(app)
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    email = db.Column(db.String(120), nullable=True)
    first_name = db.Column(db.String(20), nullable=True)
    password = db.Column(db.String(80), nullable=False)

class RegisterForm(FlaskForm):
    username = StringField(validators=[
                           InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": " "})
    email = StringField(validators=[Length(max=120)], render_kw={"placeholder": " "})
    first_name = StringField(validators=[Length(max=20)], render_kw={"placeholder": " "})
    password = PasswordField(validators=[
                             InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": " "})
    submit = SubmitField('Register')

    def validate_username(self, username):
        existing_user_username = User.query.filter_by(
            username=username.data).first()
        if existing_user_username:
            raise ValidationError(
                'That username already exists. Please choose a different one.')

    def validate_email(self, email):
        existing_user_email = User.query.filter_by(
            email=email.data).first()
        if existing_user_email:
            raise ValidationError(
                'This email is already registered. Try logging in instead.')
        
class LoginForm(FlaskForm):
    email = StringField(validators=[InputRequired()], render_kw={"placeholder": "Email"})
    password = PasswordField(validators=[
                             InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "Password"})
    submit = SubmitField('Login')

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

from flask import request, redirect, url_for, flash, render_template
from flask_login import current_user, login_user
from urllib.parse import urlparse, urljoin

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

@app.route('/login', methods=['GET', 'POST'])
def login():
    
    if current_user.is_authenticated:
        next_page = request.args.get('next')
        if next_page and is_safe_url(next_page):
            return redirect(next_page)
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Login unsuccessful. Please check your email and password.', 'danger')
    else:
        if request.method == 'POST':
            print("Form submission failed:", form.errors)

    return render_template('auth/login.html', form=form)



@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegisterForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('This email is already registered. Try logging in instead.', 'danger')
            return render_template('auth/register.html', form=form)
        
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        new_user = User(
            username=form.username.data,
            email=form.email.data,
            first_name=form.first_name.data,
            password=hashed_password
        )
        
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully! You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('auth/register.html', form=form)


@app.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    try:
        user_id = current_user.id
        User.query.filter_by(id=user_id).delete()
        db.session.commit()
        logout_user()
        return jsonify({"message": "Account deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/check_username', methods=['GET'])
def check_username():
    username = request.args.get('username')
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({'available': False})
    return jsonify({'available': True})


@app.route('/check_email', methods=['GET'])
def check_email():
    email = request.args.get('email')
    if email:
        email_exists = User.query.filter_by(email=email).first() is not None
        return jsonify({'exists': email_exists})
    return jsonify({'exists': False})


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