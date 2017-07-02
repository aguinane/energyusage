import csv
import io
import os
import datetime
import logging
import statistics
import arrow
import requests
from flask import flash, url_for
import nemreader as nr
from . import db
from .models import User, Energy, get_meter_name


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


def import_meter_data(meter_id, file_path, uom='kWh', file_type='interval'):
    """ Load data from the user uploaded csv file into the database
    """
    meter_name = get_meter_name(meter_id)
    failed_records = 0
    new_records = 0

    url = url_for('api.interval_upload', _external=True)
    headers = {'X-meterid': str(meter_id)}

    if file_type == 'interval':
        # Determine the interval spacing between rows
        interval = determine_interval(file_path)
        if interval not in [1, 10, 30]:
            msg = 'Average time interval must be 1, 10 or 30 minutes, not {}'.format(
                interval)
            flash(msg, 'danger')
            return 0, 0, 0

        for row in load_from_file(file_path):
            try:
                reading_end = parse_date(row[0])
            except ValueError:
                msg = '{} is not a date format'.format(row[0])
                logging.error(msg)
                failed_records += 1
                continue

            e1 = None
            e2 = None
            b1 = None
            try:
                e1 = row[1]
                e2 = row[2]
            except IndexError:
                pass

            payload = {'d': reading_end.strftime('%Y%m%d'),
                       't': reading_end.strftime('%H:%M'),
                       'interval': str(interval),
                       'e1': e1,
                       'e2': e2,
                       'b1': b1
                      }
            r = requests.get(url, headers=headers, data=payload)
            if r.status_code == 201:
                new_records += 1



    elif file_type == 'nem':
        try:
            m = nr.read_nem_file(file_path)
        except ValueError:
            msg = 'Could not read NEM file. Is it in the right format?'
            flash(msg, 'danger')
            return 0, 0, 0
        try:
            channels = m.readings[meter_name]
        except KeyError:
            nmis = ','.join(m.transactions.keys())
            msg = "Could not find a NMI matching '{}' in the NEM file. ".format(meter_name)
            msg += 'Check that your meter name matches one of these NMIs: {}'.format(nmis)
            flash(msg, 'danger')
            return 0, 0, 0
        for channel in channels:
            readings = []
            for reading in m.readings[meter_name][channel]:
                    readings.append(reading)
            new_records, skipped_records = load_interval_readings(
                            meter_id, channel, readings, uom)

    return new_records, skipped_records, failed_records


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
