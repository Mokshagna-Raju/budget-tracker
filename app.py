from flask import Flask, render_template, redirect, url_for, request, flash, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from datetime import datetime, date as d, date
from collections import defaultdict
from io import StringIO
from sqlalchemy import extract
import csv
from datetime import date

from models import db, User, Transaction, Goal
from flask_mail import Attachment
from email.mime.image import MIMEImage
import os



app = Flask(__name__)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'lapbro234@gmail.com'         # ✨ your Gmail ID
app.config['MAIL_PASSWORD'] = 'skoygarhhfqgjxbb'       # 🔐 App password (not regular password)
app.config['MAIL_DEFAULT_SENDER'] = 'your_email@gmail.com'   # optional, but good to keep

mail = Mail(app)

app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Token serializer
serializer = URLSafeTimedSerializer('your-secret-key')

# Generate token for a given email
def generate_token(email):
    return s.dumps(email, salt='password-reset-salt')

# Verify token (expires in 1 hour)
def verify_token(token, max_age=3600):
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=max_age)
        return email
    except Exception:
        return None

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return redirect(url_for('welcome'))

@app.route('/welcome')
def welcome():
    return render_template('welcome.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()

        if user:
            token = serializer.dumps(user.email, salt='reset-password-salt')
            reset_url = url_for('reset_password', token=token, _external=True)

            msg = Message('Password Reset Request',
                          recipients=[user.email])

            # 🟢 Add logo image path
            image_path = os.path.join('static', 'images', 'logo.png')  # use your actual file name
            with open(image_path, 'rb') as img_file:
                img_data = img_file.read()
                image = MIMEImage(img_data)
                image.add_header('Content-ID', '<logo>')
                msg.attach('logo.png', 'image/png', img_data)

            # 🟢 Use HTML body to show logo
            msg.html = f"""
            <div style="font-family: Arial, sans-serif;">
                <h2><img src="cid:logo" alt="Logo" style="height: 50px;"> Personal Budget Tracker</h2>
                <p>Hello <b>{user.username}</b>,</p>
                <p>Click the button below to reset your password:</p>
                <p><a href="{reset_url}" style="padding: 10px 20px; background-color: #28a745; color: white; text-decoration: none;">Reset Password</a></p>
                <p>If you didn't request this, you can ignore this email.</p>
            </div>
            """

            mail.send(msg)
            flash('A password reset link has been sent to your email.', 'info')
        else:
            flash('No account found with that email.', 'warning')

        return redirect(url_for('login'))

    return render_template('forgot_password.html')

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = None  # Declare user at top to prevent UnboundLocalError

    try:
        email = serializer.loads(token, salt='reset-password-salt', max_age=3600)
        user = User.query.filter_by(email=email).first()
    except (SignatureExpired, BadSignature):
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('login'))

    if user is None:
        flash('No user found with this email.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form['password']

        # Hash the password for security
        user.password = generate_password_hash(new_password)

        db.session.commit()
        flash('Your password has been updated!', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html')
# app.py or routes.py
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']  # New line
        password = generate_password_hash(request.form['password'])

        existing_user = User.query.filter(
            (User.username == username) | (User.email == email)
        ).first()
        if existing_user:
            flash('Username or email already exists')
            return redirect('/register')

        new_user = User(username=username, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful. Please log in.')
        return redirect('/login')

    return render_template('register.html')

from flask import request  # Make sure this is imported at the top

@app.route('/dashboard')
@login_required
def dashboard():
    user = current_user

    # 🔶 1. Get selected month (or use current)
    selected_month_str = request.args.get('selected_month')
    if selected_month_str:
        selected_year, selected_month = map(int, selected_month_str.split('-'))
    else:
        today = date.today()
        selected_year, selected_month = today.year, today.month
        selected_month_str = f"{selected_year}-{selected_month:02d}"

    # 🔶 2. Fetch selected month's transactions
    selected_transactions = Transaction.query.filter_by(user_id=user.id).filter(
        extract('year', Transaction.date) == selected_year,
        extract('month', Transaction.date) == selected_month
    ).all()

    income = sum(t.amount for t in selected_transactions if t.type == 'income')
    expenses = sum(t.amount for t in selected_transactions if t.type == 'expense')
    balance = income - expenses

    # 🔶 3. Check savings goal for selected month
    goal = Goal.query.filter_by(user_id=user.id, year=selected_year, month=selected_month).first()
    goal_warning = None
    if goal:
        if balance >= goal.limit_amount:
            flash("🎉 Congratulations! You've achieved your savings goal!", 'success')
        else:
            flash("⚠️ Warning: Your savings goal is not met yet.", 'warning')

    # 🔶 4. Compare with another month (optional)
    compare_month_str = request.args.get('compare_month')
    compare_expense = None
    difference_msg = None

    if compare_month_str:
        compare_year, compare_month = map(int, compare_month_str.split('-'))

        compare_transactions = Transaction.query.filter_by(user_id=user.id, type='expense').filter(
            extract('year', Transaction.date) == compare_year,
            extract('month', Transaction.date) == compare_month
        ).all()

        compare_expense = sum(t.amount for t in compare_transactions)

        difference = expenses - compare_expense
        if difference > 0:
            difference_msg = f"You spent ₹{difference:.2f} more in {selected_month_str} than in {compare_month_str}."
        elif difference < 0:
            difference_msg = f"You saved ₹{-difference:.2f} more in {selected_month_str} than in {compare_month_str}."
        else:
            difference_msg = "Your spending is the same in both months."

    return render_template('dashboard.html',
        transactions=selected_transactions,
        balance=balance,
        goal=goal,
        goal_warning=goal_warning,
        total_income=income,
        total_expenses=expenses,
        selected_month_label=selected_month_str,
        current_month_label=compare_month_str,
        selected_month_expense=expenses,
        current_month_expense=compare_expense,
        difference_msg=difference_msg
    )

@app.route('/pie-chart')
@login_required
def pie_chart():
    user_id = current_user.id
    selected_month_str = request.args.get('selected_month')

    if selected_month_str:
        selected_year, selected_month = map(int, selected_month_str.split('-'))
    else:
        today = date.today()
        selected_year, selected_month = today.year, today.month
        selected_month_str = f"{selected_year}-{selected_month:02d}"

    transactions = Transaction.query.filter_by(user_id=user_id).filter(
        extract('year', Transaction.date) == selected_year,
        extract('month', Transaction.date) == selected_month,
        Transaction.type == 'expense'
    ).all()

    category_totals = defaultdict(float)
    for t in transactions:
        category_totals[t.category] += t.amount

    return render_template('pie_chart.html',
        category_totals=category_totals,
        selected_month_label=selected_month_str
    )

@app.route('/spending_trends')
@login_required
def spending_trends():
    user_id = current_user.id
    selected_month_str = request.args.get('selected_month')

    if selected_month_str:
        selected_year, selected_month = map(int, selected_month_str.split('-'))
    else:
        today = date.today()
        selected_year, selected_month = today.year, today.month
        selected_month_str = f"{selected_year}-{selected_month:02d}"

    transactions = Transaction.query.filter_by(user_id=user_id, type='expense').filter(
        extract('year', Transaction.date) == selected_year,
        extract('month', Transaction.date) == selected_month
    ).all()

    data = defaultdict(lambda: defaultdict(float))
    for t in transactions:
        month_label = t.date.strftime('%Y-%m')
        data[t.category][month_label] += t.amount

    all_months = sorted(set(month for cat_data in data.values() for month in cat_data.keys()))

    datasets = []
    colors = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF']

    for i, (category, values) in enumerate(data.items()):
        datasets.append({
            'label': category,
            'data': [values.get(month, 0) for month in all_months],
            'borderColor': colors[i % len(colors)],
            'backgroundColor': 'rgba(0, 0, 0, 0)',
            'borderWidth': 2,
            'tension': 0.4,
            'fill': False
        })

    return render_template('spending_trends.html',
        labels=all_months,
        datasets=datasets,
        selected_month_label=selected_month_str
    )

@app.route('/compare_spending', methods=['GET', 'POST'])
@login_required
def compare_spending():
    comparison_result = None
    labels = []
    datasets = []
    bar_colors = []
    selected_months = []

    if request.method == 'POST':
        month1 = request.form['month1']  # 'YYYY-MM'
        month2 = request.form['month2']  # 'YYYY-MM'
        selected_months = [month1, month2]

        year1, m1 = map(int, month1.split('-'))
        year2, m2 = map(int, month2.split('-'))

        user_id = current_user.id

        transactions_month1 = Transaction.query.filter_by(user_id=user_id, type='expense').filter(
            extract('year', Transaction.date) == year1,
            extract('month', Transaction.date) == m1
        ).all()

        transactions_month2 = Transaction.query.filter_by(user_id=user_id, type='expense').filter(
            extract('year', Transaction.date) == year2,
            extract('month', Transaction.date) == m2
        ).all()

        total1 = sum(t.amount for t in transactions_month1)
        total2 = sum(t.amount for t in transactions_month2)

        if total2 > total1:
            comparison_result = ('More spent in second month!', 'red')
        elif total2 < total1:
            comparison_result = ('Saved compared to first month!', 'green')
        else:
            comparison_result = ('Same spending in both months!', 'gray')

        labels = ['Spending']
        datasets = [
            {
                'label': month1,
                'data': [total1],
                'backgroundColor': '#36A2EB'
            },
            {
                'label': month2,
                'data': [total2],
                'backgroundColor': '#FF6384'
            }
        ]

    return render_template(
        'compare_spending.html',
        comparison_result=comparison_result,
        labels=labels,
        datasets=datasets,
        selected_months=selected_months
    )

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/add', methods=['POST'])
@login_required
def add_transaction():
    amount = float(request.form['amount'])
    category = request.form['category']
    trans_type = request.form['type']
    note = request.form.get('note', '')
    date_str = request.form.get('date')

    if date_str:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    else:
        date = d.today()

    new_transaction = Transaction(
        amount=amount,
        category=category,
        type=trans_type,
        note=note,
        date=date,
        user_id=current_user.id
    )
    db.session.add(new_transaction)
    db.session.commit()
    flash('Transaction added!')
    return redirect(url_for('dashboard'))

@app.route('/set_goal', methods=['POST'])
@login_required
def set_goal():
    limit_amount = float(request.form['limit_amount'])
    month_year = request.form['month_year']
    year, month = map(int, month_year.split('-'))

    goal = Goal.query.filter_by(user_id=current_user.id, year=year, month=month).first()
    if goal:
        goal.limit_amount = limit_amount
    else:
        goal = Goal(user_id=current_user.id, year=year, month=month, limit_amount=limit_amount)
        db.session.add(goal)

    db.session.commit()
    flash(f'Goal set for {month_year} (₹{limit_amount})!')
    return redirect(url_for('dashboard'))

@app.route('/delete/<int:transaction_id>', methods=['POST'])
@login_required
def delete_transaction(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    if transaction.user_id != current_user.id:
        flash("Unauthorized action.")
        return redirect(url_for('dashboard'))

    db.session.delete(transaction)
    db.session.commit()
    flash('Transaction deleted.')
    return redirect(url_for('dashboard'))

@app.route('/download')
@login_required
def download_csv():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()

    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['Date', 'Type', 'Category', 'Amount', 'Note'])

    for t in transactions:
        writer.writerow([t.date, t.type, t.category, t.amount, t.note or ''])

    output = si.getvalue()
    si.close()

    return Response(
        output,
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=transactions.csv"}
    )

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)

