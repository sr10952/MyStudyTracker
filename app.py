from datetime import datetime as dt
import datetime
from flask_sqlalchemy import SQLAlchemy
from flask import Flask, redirect, url_for, session, render_template, request, g
from authlib.integrations.flask_client import OAuth
import os

app = Flask(__name__)
oauth = OAuth(app)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')

#Google Config
google = oauth.register(
    name='google',
    client_id='get your own', #or ask me for one
    client_secret='see above',
    access_token_url='https://oauth2.googleapis.com/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',  # This gets the user's profile information
    jwks_uri='https://www.googleapis.com/oauth2/v3/certs',
    client_kwargs={'scope': 'openid email profile'}

)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://username:password@localhost/mystudytracker'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
class User(db.Model):
    __tablename__ = 'Users'  # specify the actual table name here
    UserID = db.Column(db.Integer, primary_key=True)
    Username = db.Column(db.String(50), nullable=False)
    GoogleID = db.Column(db.String(255), unique=True, nullable=True)

class StudyInformation(db.Model):
    __tablename__ = 'StudyInformation'  # specify the actual table name here
    RecordID = db.Column(db.Integer, primary_key=True)
    UserID = db.Column(db.Integer, db.ForeignKey('Users.UserID'), nullable=False)  # use actual table name
    TimingID = db.Column(db.Integer, db.ForeignKey('StudyTimings.TimingID'), nullable=False)  # use actual table name
    Hours = db.Column(db.Float, nullable=False)
    Date = db.Column(db.Date, nullable=False)

class StudyTiming(db.Model):
    __tablename__ = 'StudyTimings'  
    TimingID = db.Column(db.Integer, primary_key=True)
    TimingName = db.Column(db.String(20), nullable=False)


@app.before_request
def load_user():
    user = session.get('user', None)
    if user:
        # User is logged in
        g.user = user
    else:
        # User is not logged in
        g.user = None

def hours_to_hhmm(hours):
    # Convert hours to total minutes
    total_minutes = round(hours * 60)
    # Round to the nearest 5 minutes
    total_minutes = 5 * round(total_minutes / 5)
    # Get hours and minutes
    hh = total_minutes // 60
    mm = total_minutes % 60
    return f"{hh:02d}:{mm:02d}"


@app.route('/')
def index():
    return "Welcome to MyStudyTracker!"

@app.route('/login')
def login():
    return google.authorize_redirect(url_for('authorize', _external=True))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

@app.route('/authorize')
def authorize():
    try:
        response = google.authorize_access_token()
        if not response:
            return 'Access token was not retrieved successfully.', 401

        user_info = google.get('userinfo').json()
        if not user_info:
            return 'User info was not retrieved successfully.', 401

        # Use 'id' as the unique identifier
        google_id = user_info['id']

        # Check if this Google ID is already in the database
        user = User.query.filter_by(GoogleID=google_id).first()

        if not user:
            # Insert the new user into the database
            new_user = User(Username=user_info['name'], GoogleID=google_id)
            db.session.add(new_user)
            db.session.commit()
            user_id = new_user.UserID
        else:
            # User already exists, get the existing user's ID
            user_id = user.UserID

        # Set the user information in the session
        session['user'] = user_info
        session['user_id'] = user_id  # Store the user's database ID in the session for later use

        return redirect('/')
    except Exception as e:
        return f'An error occurred: {str(e)}'


@app.route('/statistics')
def statistics():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    # Query for 7 Days Sum
    seven_days_sum = db.session.query(
        StudyInformation.Date, db.func.sum(StudyInformation.Hours)
    ).filter(
        StudyInformation.UserID == user_id,
        StudyInformation.Date >= datetime.datetime.now() - datetime.timedelta(days=7)
    ).group_by(StudyInformation.Date).all()
    seven_days_sum = [(timing[0], hours_to_hhmm(timing[1])) for timing in seven_days_sum]

    # Query for 7 Days Average
    sum_query = db.session.query(db.func.sum(StudyInformation.Hours)).filter(
        StudyInformation.UserID == user_id,
        StudyInformation.Date >= datetime.datetime.now() - datetime.timedelta(days=7)
    ).subquery()
    seven_days_avg = db.session.query(
        (db.func.coalesce(sum_query.columns[0], 0) / 7).label("THours")
    ).one()

    # Query for Daily by Slot
    daily_by_slot = db.session.query(
    StudyInformation.Date,
    db.func.sum(db.case((StudyTiming.TimingName == 'BeforeShachris', StudyInformation.Hours), else_=0)).label('BeforeShachrisHours'),
    db.func.sum(db.case((StudyTiming.TimingName == 'AM', StudyInformation.Hours), else_=0)).label('AMHours'),
    db.func.sum(db.case((StudyTiming.TimingName == 'PM', StudyInformation.Hours), else_=0)).label('PMHours'),
    db.func.sum(db.case((StudyTiming.TimingName == 'Night', StudyInformation.Hours), else_=0)).label('NightHours'),
    db.func.sum(StudyInformation.Hours).label('TotalDailyHours')
    ).join(
        StudyTiming, StudyInformation.TimingID == StudyTiming.TimingID
    ).filter(
        StudyInformation.UserID == user_id
    ).group_by(StudyInformation.Date).order_by(StudyInformation.Date).all()



    return render_template('statistics.html', seven_days_sum=seven_days_sum, seven_days_avg=seven_days_avg, daily_by_slot=daily_by_slot)

@app.route('/add_study_time', methods=['GET', 'POST'])
def add_study_time():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    today = dt.today().date()

    if request.method == 'POST':
        # Get form data
        Timing_ID = request.form['timing_id']
        hours = int(request.form['hours'])
        minutes = int(request.form['minutes'])

        # Convert hours and minutes to decimal
        total_hours = hours + minutes / 60.0
        total_hours = round(total_hours, 1)

        date = request.form['date']
        new_study_time = StudyInformation(UserID=user_id, TimingID=Timing_ID, Hours=total_hours, Date=date)
        db.session.add(new_study_time)
        db.session.commit()

        return 'Study time added successfully'
    else:
        timings = StudyTiming.query.all()
        todays_study = db.session.query(
            StudyTiming.TimingName,
            db.func.sum(StudyInformation.Hours).label('total_hours')
        ).join(
            StudyTiming, StudyInformation.TimingID == StudyTiming.TimingID
        ).filter(
            StudyInformation.UserID == user_id,
            StudyInformation.Date == today
        ).group_by(StudyTiming.TimingName).all()
        todays_study = [(timing[0], hours_to_hhmm(timing[1])) for timing in todays_study]
        timings = StudyTiming.query.all()
        return render_template('add_study_time.html', 
                        timings=timings, 
                        default_date=dt.today().strftime('%Y-%m-%d'),
                        todays_study=todays_study)


if __name__ == '__main__':
    app.run(debug=True)
