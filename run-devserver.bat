pip install -r requirements.txt
python helpers.py first-run
set FLASK_APP=run.py
set FLASK_ENV=development
flask run --host=0.0.0.0