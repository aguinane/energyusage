"""
    energy.api
    ~~~~~~~~~
    Define the energy site API
"""

import datetime
from collections import namedtuple
from flask import Blueprint, jsonify, request
from .models import Energy, get_data_range
from . import db

Record = namedtuple('Record', ['reading_start', 'reading_end',
                               'E1', 'E2', 'B1', 'V', 'T'])


api = Blueprint('api', __name__)


@api.route('/api/v1.0/data-range', methods=['GET'])
def data_range():
    """ Get the available data range of a meter """
    try:
        meter_id = request.headers['X-meterid']
    except KeyError:
        try:
            meter_id = request.values['meterid']
        except KeyError:
            msg = 'ERROR: Must specify a HTTP header of meterid '
            return msg, 400
    first_record, last_record = get_data_range(meter_id)

    return jsonify({'first_record': first_record,
                    'last_record': last_record
                    })


@api.route('/api/v1.0/interval-upload', methods=['POST'])
def interval_upload():
    try:
        meter_id = request.headers['X-meterid']
    except KeyError:
        msg = 'ERROR: Must specify a HTTP header of meterid '
        return msg, 400

    interval_data = request.json
    try:
        date = interval_data['d']
        time = interval_data['t']
    except KeyError:
        msg = 'ERROR: Must specify a date and time '
        return msg, 400

    try:
        timestamp = '{} {}'.format(date, time)
        interval_end = datetime.datetime.strptime(timestamp, '%Y%m%d %H:%M')
    except ValueError:
        msg = 'ERROR: Date or time in wrong format'
        return msg, 400

    try:
        interval = int(interval_data['interval'])
    except KeyError:
        msg = 'ERROR: Must specify consumption'
        return msg, 400
    interval_start = interval_end - \
        datetime.timedelta(seconds=interval * 60)
    try:
        e1 = interval_data['e1']
    except KeyError:
        msg = 'ERROR: Must specify consumption'
        return msg, 400

    try:
        e2 = interval_data['e2']
    except KeyError:
        e2 = None

    try:
        b1 = interval_data['b1']
    except KeyError:
        b1 = None

    try:
        v = interval_data['v']
    except KeyError:
        v = None

    try:
        t = interval_data['t']
    except KeyError:
        t = None

    reading = Record(interval_start, interval_end,
                     e1, e2, b1, v, t)

    x = load_interval_reading(meter_id, reading)
    if x == 400:
        msg = 'ERROR: Record already exists'
        return msg, 400

    return jsonify({'meter_id': meter_id,
                    'reading': reading
                    }
                   ), 201


def load_interval_reading(meter_id, record):
    """ Load reading into database """
    existing = Energy.query.filter_by(meter_id=meter_id,
                                      reading_start=record.reading_start
                                      ).first()
    if existing:
        return 400
    else:
        energy = Energy(meter_id=meter_id,
                        reading_start=record.reading_start,
                        reading_end=record.reading_end,
                        e1=record.E1,
                        e2=record.E2,
                        b1=record.B1,
                        voltage=record.V,
                        temp=record.T)
        db.session.add(energy)
    db.session.commit()
    return 201
