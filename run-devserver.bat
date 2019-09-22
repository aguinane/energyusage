pip install -r requirements.txt --user
python helpers.py first-run
set FLASK_APP=run.py
set FLASK_ENV=development
explorer "http://localhost:5000"
flask run --host=0.0.0.0