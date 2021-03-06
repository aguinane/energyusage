"""
    energy.api
    ~~~~~~~~~
    Define the energy site API
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base


app = Flask(__name__)
app.config.from_object("config")

db = SQLAlchemy(app)

from .models import User

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "signin"

from energy.api import api

app.register_blueprint(api)

from energy.meters import meters  # noqa

app.register_blueprint(meters, url_prefix="/meters")

from energy.views import *


@login_manager.user_loader
def load_user(userid):
    return User.query.filter(User.user_id == userid).first()
