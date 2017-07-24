"""
    energy.api
    ~~~~~~~~~
    Define the energy site API
"""

import datetime
from collections import namedtuple
from flask import Blueprint, jsonify, request
from .models import Energy, get_data_range, get_meter_api_key
from . import db

Record = namedtuple('Record', ['reading_start', 'reading_end',
                               'E1', 'E2', 'B1', 'V', 'T'])


api = Blueprint('api', __name__)


@api.route('/api/v1.0/data-range', methods=['GET'])
def data_range():
    """ Get the available data range of a meter """
    try:
        meter_id = int(request.headers['X-meterid'])
    except KeyError:
        try:
            meter_id = int(request.values['meterid'])
        except KeyError:
            msg = 'ERROR: Must specify a HTTP header of meterid '
            return msg, 400
    first_record, last_record = get_data_range(meter_id)

    return jsonify({'first_record': first_record,
                    'last_record': last_record
                    })


@api.route('/api/v1.0/interval-upload', methods=['POST'])
def interval_upload():
    """ API to add new interval readings """

    try:
        meter_id = int(request.headers['X-meterid'])
    except KeyError:
        msg = 'Must specify a HTTP header of X-meterid '
        return jsonify({'errors': msg
                        }), 400

    try:
        api_key = request.headers['X-apikey']
    except KeyError:
        msg = 'Must specify a HTTP header of X-apikey '
        return jsonify({'errors': msg
                }), 400

    if api_key == get_meter_api_key(meter_id):
        pass
    else:
        msg = 'Invalid API Key'
        return jsonify({'errors': msg
                }), 403

    new_readings = 0
    skipped_readings = 0
    failed_readings = 0
    errors = []
    interval_data = request.json
    for record in interval_data:
        try:
            date = record['date']
            time = record['time']
        except KeyError:
            msg = 'Must specify a date and time '
            errors.append(msg)
            failed_readings += 1
            continue

        try:
            timestamp = '{} {}'.format(date, time)
            interval_end = datetime.datetime.strptime(timestamp, '%Y%m%d %H:%M')
        except ValueError:
            msg = 'ERROR: Date or time in wrong format'
            errors.append(msg)
            failed_readings += 1
            continue

        try:
            interval = int(record['interval'])
        except KeyError:
            msg = 'ERROR: Must specify consumption'
            errors.append(msg)
            failed_readings += 1
            continue
        interval_start = interval_end - \
            datetime.timedelta(seconds=interval * 60)
        try:
            e1 = record['e1']
        except KeyError:
            msg = 'ERROR: Must specify consumption'
            errors.append(msg)
            failed_readings += 1
            continue

        try:
            e2 = record['e2']
        except KeyError:
            e2 = None

        try:
            b1 = record['b1']
        except KeyError:
            b1 = None

        try:
            v = record['v']
        except KeyError:
            v = None

        try:
            t = record['t']
        except KeyError:
            t = None

        reading = Record(interval_start, interval_end,
                        e1, e2, b1, v, t)

        x = load_interval_reading(meter_id, reading, commit=False)
        if x == 1:
            new_readings += 1
        else:
            skipped_readings += 1

    db.session.commit()

    return jsonify({'meter_id': meter_id,
                    'added': new_readings,
                    'skipped': skipped_readings,
                    'failed': failed_readings,
                    'errors': errors
                    }
                ), 201


def load_interval_reading(meter_id, record, commit=True):
    """ Load reading into database """
    existing = Energy.query.filter_by(meter_id=meter_id,
                                      reading_start=record.reading_start
                                      ).first()
    if existing:
        return 0
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
        if commit:
            db.session.commit()
        return 1
