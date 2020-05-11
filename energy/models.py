import datetime
import os
from sqlalchemy import create_engine
from sqlalchemy import MetaData, Table, Column, DateTime, Float, Integer, ForeignKey
from sqlalchemy import between, func
from sqlalchemy.sql import select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import Column, String, DateTime, Float, Integer

from werkzeug.security import generate_password_hash, check_password_hash

from . import db, app


class Meter(db.Model):
    """ A list of meters """

    __tablename__ = "meter"
    meter_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.user_id"))
    sharing = Column(String(7))  # Public / Private
    api_key = Column(String(36))
    meter_name = Column(String(20))


def delete_meter_data(meter_id):
    """ Delete meter and all data """
    Meter.query.filter(Meter.meter_id == meter_id).delete()
    db.session.commit()
    db_loc = f"data/meter_{meter_id}.db"
    if os.path.isfile(db_loc):
        os.remove(db_loc)


def get_meter_name(meter_id):
    """ Return a list of meters that the user manages """
    meter = Meter.query.filter(Meter.meter_id == meter_id).first()
    return meter.meter_name


def get_meter_api_key(meter_id):
    """ Return the API key for the meter """
    meter = Meter.query.filter(Meter.meter_id == meter_id).first()
    return meter.api_key


def get_user_meters(user_id):
    """ Return a list of meters that the user manages """
    meters = Meter.query.filter(Meter.user_id == user_id)
    for meter in meters:
        user_name = User.query.filter_by(user_id=meter.user_id).first().username
        yield (meter.meter_id, meter.meter_name, user_name)


def get_public_meters():
    """ Return a list of publicly viewable meters """
    meters = Meter.query.filter(Meter.sharing == "public")
    for meter in meters:
        user_name = User.query.filter_by(user_id=meter.user_id).first().username
        yield (meter.meter_id, meter.meter_name, user_name)


def visible_meters(user_id):
    """ Return a list of meters that the user can view """
    if user_id:
        meters = Meter.query.filter(
            (Meter.user_id == user_id) | (Meter.sharing == "public")
        )
    else:
        meters = Meter.query.filter(Meter.sharing == "public")
    for meter in meters:
        user_name = User.query.filter_by(user_id=meter.user_id).first().username
        yield (meter.meter_id, meter.meter_name, user_name)


class User(db.Model):
    """ A user account """

    __tablename__ = "user"
    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    apikey = Column(String(128))

    def __repr__(self):
        return "<User {}>".format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_active(self):
        """True, as all users are active."""
        return True

    def get_id(self):
        """Return the email address to satisfy Flask-Login's requirements."""
        return self.user_id

    def is_authenticated(self):
        """Return True if the user is authenticated."""
        return True

    def is_anonymous(self):
        """False, as anonymous users aren't supported."""
        return False
