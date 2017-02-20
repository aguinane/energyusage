import csv
import io
import os
import arrow
import datetime
from .models import User, Energy
from . import db
from flask import flash
import logging
import statistics


def export_meter_data(user_id):

    header = ['CHANNEL', 'READING_START', 'READING_END', 'VALUE']
    data = get_meter_data(user_id)
    return construct_csv(header, data)


def get_meter_data(user_id):
    readings = Energy.query.filter(Energy.meter_id == user_id)
    for r in readings:
        yield [r.meter_channel, r.reading_start, r.reading_end, r.value]


def construct_csv(header, data):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header)
    for row in data:
        writer.writerow(row)
    return output.getvalue()


def import_meter_data(user_name, file_path):
    """ Load data from the user uploaded csv file into the database
    """
    user = User.query.filter_by(username=user_name).first()

    interval = determine_interval(file_path)
    if interval not in [1, 10, 30]:
        msg = 'Average time interval must be 1, 10 or 30 minutes, not {}'.format(
            interval)
        flash(msg, 'danger')
        return 0, 0, 0

    imp_records = []
    exp_records = []
    failed_records = 0
    for row in load_from_file(file_path):
        try:
            reading_end = parse_date(row[0])
            reading_start = reading_end - datetime.timedelta(seconds=interval * 60)
        except:
            msg = '{} is not a date format'.format(row[0])
            logging.error(msg)
            failed_records += 1
            continue

        if row[1]:
            imp = float(row[1])
            imp_records.append((reading_start, reading_end, imp))
        try:
            if row[2]:
                exp = float(row[2])
                exp_records.append((reading_start, reading_end, exp))
        except IndexError:
            pass

    new_records, skipped_records = load_interval_readings(user.id, 'Imp', imp_records)
    if exp_records:
        new_records, skipped_records = load_interval_readings(user.id, 'Exp', exp_records)

    return new_records, skipped_records, failed_records

def load_interval_readings(meter_id, meter_channel, readings):
    """ Load readings into database """
    new_records = 0
    skipped_records = 0
    for row in readings:
        reading_start = row[0]
        reading_end = row[1]
        value = row[2]
        if Energy.query.filter_by(meter_id=meter_id, meter_channel=meter_channel,
                                reading_start=reading_start).first():
            # Record already exists
            skipped_records += 1
            continue
        else:
            energy = Energy(meter_id=meter_id,
                            meter_channel=meter_channel,
                            reading_start=reading_start,
                            reading_end=reading_end,
                            value=value)
            db.session.add(energy)
            new_records += 1
    db.session.commit()
    return new_records, skipped_records


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
        VALID_HEADINGS = [['READING_DATETIME', 'IMP'],
                          ['READING_DATETIME', 'IMP', 'EXP'],
                          ['READING_DATETIME', 'IMP', 'EXP', 'STATUS'],
                          ['READING_DATE', 'IMP', 'EXP']
                          ]
        if h in VALID_HEADINGS:
            for row in reader:
                yield row
        else:
            flash('CSV was not in the correct format.', category='danger')
