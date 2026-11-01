@echo off
cd /d "%~dp0backend"
if not exist database\career_ai.db python database\init_db.py
python app.py
pause
