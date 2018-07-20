from sqlalchemy import create_engine
from sqlalchemy import MetaData, Table, Column, DateTime, Float, Integer, between, func
from sqlalchemy.sql import select
from sqlalchemy.ext.hybrid import hybrid_property
import datetime
from . import bcrypt, db, app


class Meter(db.Model):
    """ A list of meters
    """
    meter_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'))
    sharing = db.Column(db.String(7)) # Public / Private
    api_key = db.Column(db.String(36))
    meter_name = db.Column(db.String(20))


def delete_meter_data(meter_id):
    """ Delete meter and all data """
    Energy.query.filter(Energy.meter_id==meter_id).delete()
    Meter.query.filter(Meter.meter_id==meter_id).delete()
    db.session.commit()


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
    meters = Meter.query.filter(Meter.sharing == 'public')
    for meter in meters:
        user_name = User.query.filter_by(user_id=meter.user_id).first().username
        yield (meter.meter_id, meter.meter_name, user_name)


def visible_meters(user_id):
    """ Return a list of meters that the user can view """
    if user_id:
        meters = Meter.query.filter((Meter.user_id == user_id)|(Meter.sharing == 'public'))
    else:
        meters = Meter.query.filter(Meter.sharing == 'public')
    for meter in meters:
        user_name = User.query.filter_by(user_id=meter.user_id).first().username
        yield (meter.meter_id, meter.meter_name, user_name)


class Energy(db.Model):
    """ The energy data for a user
    """
    meter_id = db.Column(db.Integer, db.ForeignKey('meter.meter_id'), primary_key=True)
    reading_start = db.Column(db.DateTime, primary_key=True)
    reading_end = db.Column(db.DateTime)
    e1 = db.Column(db.Integer)
    e2 = db.Column(db.Integer)
    b1 = db.Column(db.Integer)
    voltage = db.Column(db.Float)
    temp = db.Column(db.Float)


def get_data_range(meter_id):
    """ Get the minimum and maximum date ranges with data
    """
    min_date = db.session.query(func.min(Energy.reading_start)).filter(Energy.meter_id==meter_id).scalar()
    max_date = db.session.query(func.max(Energy.reading_end)).filter(Energy.meter_id==meter_id).scalar()
    if max_date:
        max_date = max_date - datetime.timedelta(hours=1/6)
    return (min_date, max_date)


class User(db.Model):
    """ A user account
    """
    user_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(64), unique=True)
    _password = db.Column(db.String(128))
    apikey = db.Column(db.String(64))

    @hybrid_property
    def password(self):
        return self._password

    @password.setter
    def _set_password(self, plaintext):
        self._password = bcrypt.generate_password_hash(plaintext)

    def is_correct_password(self, plaintext):
        return bcrypt.check_password_hash(self._password, plaintext)

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
