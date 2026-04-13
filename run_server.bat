@echo off
REM Change directory to your project folder
cd /d C:\Users\Tshumba\Documents\Work Documents\Work Apps\teams_clone_app Oct-14 fully enhanced

REM Activate the virtual environment
call venv\Scripts\activate.bat

REM Set the Flask app
set FLASK_APP=app.py

REM Run Flask on host 0.0.0.0 and port 8000
python -m flask run --host=0.0.0.0 --port=8000

pause
