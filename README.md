# energyusage
[![Build Status](https://travis-ci.org/aguinane/energyusage.svg?branch=develop)](https://travis-ci.org/aguinane/energyusage)

Provide analysis and charting of energy usage

[🔗 Site Link](http://aguinane.pythonanywhere.com/)


## Run yourself

To run the website:
```
python run.py
```
This will set up the sqlite database automatically on first run.

Or in headless mode:
```
setsid gunicorn --bind 0.0.0.0:8000 wsgi:app -t 600
```

