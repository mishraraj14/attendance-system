from flask import Flask, render_template, request, redirect, flash, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import os, datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret123'

# DATABASE
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'db.sqlite3')
db = SQLAlchemy(app)

# LOGIN
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# EMAIL
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'
app.config['MAIL_PASSWORD'] = 'your_app_password'

mail = Mail(app)

# MODELS
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    password = db.Column(db.String(200))
    role = db.Column(db.String(20))

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    roll = db.Column(db.String(20))

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer)
    date = db.Column(db.String(20))
    status = db.Column(db.String(10))

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ROUTES

@app.route('/')
@login_required
def dashboard():
    total = Student.query.count()
    present = Attendance.query.filter_by(status='Present').count()
    absent = Attendance.query.filter_by(status='Absent').count()

    percent = 0
    if present + absent > 0:
        percent = round((present/(present+absent))*100,2)

    return render_template('dashboard.html', students=total, present=present, absent=absent, percent=percent)

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()

        if user and check_password_hash(user.password, request.form['password']):
            login_user(user)
            return redirect('/')
        else:
            flash('Invalid login')

    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect('/login')

@app.route('/add', methods=['GET','POST'])
@login_required
def add():
    if current_user.role != 'admin':
        return "Access Denied"

    if request.method == 'POST':
        s = Student(name=request.form['name'], roll=request.form['roll'])
        db.session.add(s)
        db.session.commit()
        return redirect('/')

    return render_template('add.html')

@app.route('/mark', methods=['GET','POST'])
@login_required
def mark():
    students = Student.query.all()

    if request.method == 'POST':
        for s in students:
            status = request.form.get(str(s.id))
            if status:
                db.session.add(Attendance(
                    student_id=s.id,
                    date=str(datetime.date.today()),
                    status=status
                ))
        db.session.commit()
        return redirect('/')

    return render_template('mark.html', students=students)

@app.route('/view')
@login_required
def view():
    data = Attendance.query.all()
    return render_template('view.html', data=data, Student=Student)

@app.route('/report')
@login_required
def report():
    students = Student.query.all()
    result = []

    for s in students:
        total = Attendance.query.filter_by(student_id=s.id).count()
        present = Attendance.query.filter_by(student_id=s.id, status='Present').count()

        percent = 0
        if total > 0:
            percent = round((present/total)*100,2)

        if percent < 75:
            send_email(s.name, percent)

        result.append({'name': s.name, 'percent': percent})

    return render_template('report.html', data=result)

def send_email(name, percent):
    msg = Message('Attendance Alert',
                  sender=app.config['MAIL_USERNAME'],
                  recipients=['receiver@gmail.com'])
    msg.body = f"{name} has low attendance: {percent}%"
    mail.send(msg)

@app.route('/export')
@login_required
def export():
    data = Attendance.query.all()
    csv = "Name,Date,Status\n"

    for d in data:
        s = db.session.get(Student, d.student_id)
        if s:
            csv += f"{s.name},{d.date},{d.status}\n"

    return Response(csv,
        mimetype="text/csv",
        headers={"Content-disposition":"attachment; filename=data.csv"})

# INIT
with app.app_context():
    db.create_all()
    if not User.query.first():
        db.session.add(User(username='admin', password=generate_password_hash('admin'), role='admin'))
        db.session.add(User(username='teacher', password=generate_password_hash('teacher'), role='teacher'))
        db.session.commit()

if __name__ == '__main__':
    app.run()