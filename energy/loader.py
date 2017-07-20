import csv
import io
import os
import datetime
import logging
import statistics
import arrow
import requests
from flask import flash, url_for, jsonify
import nemreader as nr
from . import db
from .models import User, Energy, get_meter_name, get_meter_api_key

def export_meter_data(user_id):

    header = ['READING_START', 'READING_END', 'E1', 'E2', 'B1']
    data = get_meter_data(user_id)
    return construct_csv(header, data)


def get_meter_data(meter_id):
    readings = Energy.query.filter(Energy.meter_id == meter_id)
    for r in readings:
        yield [r.reading_start, r.reading_end, r.e1, r.e2, r.b1]


def construct_csv(header, data):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    for row in data:
        writer.writerow(row)
    return output.getvalue()



def process_meter_data(meter_id, file_path, uom='kWh', file_type='interval'):
    """ Process meter data file into json object payload to load """

    payload = []
    if file_type == 'interval':
        # Determine the interval spacing between rows
        interval = determine_interval(file_path)
        if interval not in [1, 5, 10, 15, 30]:
            msg = 'Average time interval must be 1, 5, 10, 15 or 30 minutes, not {}'.format(
                interval)
            flash(msg, 'danger')
            return []
        
        for row in load_from_file(file_path):
            try:
                reading_end = parse_date(row[0])
            except ValueError:
                msg = 'Error: {} is not a date format'.format(row[0])
                flash(msg)
                return []
            e1 = None
            e2 = None
            b1 = None
            try:
                e1 = row[1]
                e2 = row[2]
            except IndexError:
                pass

            payload.append({'date': reading_end.strftime('%Y%m%d'),
                            'time': reading_end.strftime('%H:%M'),
                            'interval': str(interval),
                            'e1': e1,
                            'e2': e2,
                            'b1': b1
                            })

    elif file_type == 'nem':
        meter_name = get_meter_name(meter_id)
        try:
            m = nr.read_nem_file(file_path)
        except ValueError:
            msg = 'Could not read NEM file. Is it in the right format?'
            flash(msg, 'danger')
            return []
        try:
            channels = m.readings[meter_name]
        except KeyError:
            nmis = ','.join(m.transactions.keys())
            msg = "Could not find a NMI matching '{}' in the NEM file. ".format(meter_name)
            msg += 'Check that your meter name matches one of these NMIs: {}'.format(nmis)
            flash(msg, 'danger')
            return []
        
        try:
            test_rows = m.readings[meter_name]['E1']
        except KeyError:
            msg = "NEM data must have an E1 channel"
            flash(msg, 'danger')
            return []

        for i, reading in enumerate(m.readings[meter_name]['E1']):
            reading_end = reading.t_end
            e1 = reading.read_value
            try:
                e2 = m.readings[meter_name]['E2'][i].read_value
            except KeyError:
                e2 = None
            try:
                b1 = m.readings[meter_name]['B1'][i].read_value
            except KeyError:
                b1 = None

            payload.append({'date': reading_end.strftime('%Y%m%d'),
                            'time': reading_end.strftime('%H:%M'),
                            'interval': '10',
                            'e1': e1,
                            'e2': e2,
                            'b1': b1
                            })

    return payload


def import_meter_data(meter_id, file_path, uom='kWh', file_type='interval'):
    """ Load data from the user uploaded csv file into the database
    """

    url = url_for('api.interval_upload', _external=True)
    headers = {'X-meterid': str(meter_id),
               'X-apikey': get_meter_api_key(meter_id)}

    payload = process_meter_data(meter_id, file_path, uom, file_type)

    r = requests.post(url, json=payload, headers=headers)
    
    if r.status_code == 201:
        results = r.json()
        return results['added'], results['skipped'], results['failed']
    else:
        return 0, 0


def get_unit_conversion(uom):
    """ Get conversion factor for passed unit """
    uom = uom.lower()
    if uom == 'wh':
        return 1
    elif uom == 'kwh':
        return 1000
    elif uom == 'wm':
        return 1 / 60
    else:
        raise ValueError('{} is not supported'.format(uom))


def determine_interval(file_path):
    """ Determine the interval of the metering data
    """

    dates = []
    for row in load_from_file(file_path):
        try:
            reading_date = parse_date(row[0])
        except:
            reading_date = None
        dates.append(reading_date)

    intervals = []
    for i, reading in enumerate(dates):
        if i > 1:
            start = dates[i - 1]
            end = reading
            if start and end:  # Not None
                interval = (end - start).seconds / 60  # Minutes
                intervals.append(interval)
    try:
        interval = round(statistics.mean(intervals), 0)
    except:
        interval = 0
    return int(interval)


def parse_date(date_string):
    try:
        return arrow.get(date_string).datetime
    except arrow.parser.ParserError:
        try:
            return arrow.get(date_string, 'DD/MM/YYYY HH:mm:ss').datetime
        except arrow.parser.ParserError:
            try:
                return arrow.get(date_string, 'DD/MM/YYYY H:mm').datetime
            except arrow.parser.ParserError:
                return arrow.get(date_string, 'D/MM/YYYY H:mm').datetime
    except:
        raise


def load_from_file(file_path):
    """ Return load data from csv
    """
    ext = os.path.splitext(file_path)[1]
    if ext == 'csv':
        flash('File should be .csv not ' + str(ext), category='danger')

    with open(file_path, newline='') as csv_file:
        reader = csv.reader(csv_file, delimiter=',', quotechar='"')
        h = next(reader, None)  # first row is headings
        if len(h) <= 4:
            for row in reader:
                yield row
