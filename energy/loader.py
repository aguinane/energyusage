import csv
import io
import os
import arrow
import datetime
from .models import User, Energy, get_meter_name
from . import db
from flask import flash
import logging
import statistics
import nemreader as nr


def export_meter_data(user_id):

    header = ['CHANNEL', 'READING_START', 'READING_END', 'VALUE']
    data = get_meter_data(user_id)
    return construct_csv(header, data)


def get_meter_data(meter_id):
    readings = Energy.query.filter(Energy.meter_id == meter_id)
    for r in readings:
        yield [r.meter_channel, r.reading_start, r.reading_end, r.value]


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
    if file_type == 'interval':
        # Determine the innterval spacing between rows
        interval = determine_interval(file_path)
        if interval not in [1, 10, 30]:
            msg = 'Average time interval must be 1, 10 or 30 minutes, not {}'.format(
                interval)
            flash(msg, 'danger')
            return 0, 0, 0

        imp_records = []
        exp_records = []

        for row in load_from_file(file_path):
            try:
                reading_end = parse_date(row[0])
                reading_start = reading_end - \
                    datetime.timedelta(seconds=interval * 60)
            except ValueError:
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

        new_records, skipped_records = load_interval_readings(
            meter_id, 'E1', imp_records, uom)
        if exp_records:
            new_records, skipped_records = load_interval_readings(
                meter_id, 'B1', exp_records, uom)

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


def load_interval_readings(meter_id, meter_channel, readings, uom='kWh'):
    """ Load readings into database (in Wh) """
    new_records = 0
    skipped_records = 0
    for row in readings:
        reading_start = row[0]
        reading_end = row[1]
        try:
            reading_uom = reading.uom
        except NameError:
            reading_uom = uom
        value = round(row[2] * get_unit_conversion(reading_uom), 2)
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
