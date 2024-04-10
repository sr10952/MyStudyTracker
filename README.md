# MyStudyTracker

## Introduction
MyStudyTracker is a Flask application for tracking study times. currently in development
supports add_study_time and statistics
works only on localhost... 

## Installation
1. Install Python and pip.
2. Install MySQL.

## Setup
1. Clone the repository: `gh repo clone sr10952/MyStudyTracker`
2. Install dependencies: `pip install -r requirements.txt`
3. Set the environment variables for Google OAuth (`GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`) and database URI (`DATABASE_URL`).
4. Initialize the database: `python init_db.py`

## Running the Application
Run the application using: `python app.py`

## Additional Configuration
- Set up your Google OAuth credentials in the Google Cloud Platform console.
