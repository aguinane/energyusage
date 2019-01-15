"""
    energy.meter
    ~~~~~~~~~
    Module for routes relating to a specific meter
"""

import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Optional, Tuple
from flask import Blueprint, render_template, redirect, url_for
from flask import request, flash, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from werkzeug.utils import secure_filename
import pytz
from metering import load_nem_data
from metering import get_load_energy_readings
from metering import get_daily_energy_readings
from metering import get_monthly_energy_readings
from metering import get_data_range, get_month_ranges
from metering import LOAD_CHS, CONTROL_CHS, GENERATION_CHS
from energy_shaper import split_into_profiled_intervals
from energy_shaper import group_into_profiled_intervals

from . import app, db
from .views import get_user_meters
from .views import get_public_meters
from .forms import FileForm, NewMeter, MeterDetails
from .models import get_meter_name
from .models import User, Meter, delete_meter_data
from .models import get_user_meters, get_public_meters, visible_meters
from .charts import monthly_bill_data

meters = Blueprint("meters", __name__, template_folder="templates")


@meters.route("/")
def index():
    """ List of available meters """
    user_id, _ = get_user_details()
    user_meters = list(get_user_meters(user_id))
    public_meters = list(get_public_meters())
    return render_template(
        'meters/meters.html',
        user_meters=user_meters,
        public_meters=public_meters)


def get_user_details():
    """ Get details of loggged in user """
    try:
        __ = current_user.username
    except AttributeError:
        return None, None
    user = User.query.filter_by(username=current_user.username).first()
    return user.user_id, user.username


def meter_visible(meter_id: int) -> bool:
    """ Return if user is authorised to see a meter """
    user_id, __ = get_user_details()
    for meter, __, __ in visible_meters(user_id):
        if meter_id == meter:
            return True
    return False


def meter_editable(meter_id: int) -> bool:
    """ Return if user is authorised to edit a meter """
    user_id, __ = get_user_details()
    for meter, __, __ in get_user_meters(user_id):
        if meter_id == meter:
            return True
    return False


@meters.route('/<int:meter_id>/manage/details', methods=["GET", "POST"])
@login_required
def manage_meter(meter_id):
    """ Manage meter details """

    if not meter_editable(meter_id):
        msg = 'Not authorised to manage this meter.'
        flash(msg, category='warning')
        return redirect(url_for('meters.index'))

    meter = Meter.query.filter_by(meter_id=meter_id).first()
    form = MeterDetails()
    if form.validate_on_submit():
        meter.meter_name = form.meter_name.data.upper().strip()
        meter.sharing = form.sharing.data
        db.session.commit()
        flash('Meter updated', category='success')
        return redirect(url_for('meters.manage_meter', meter_id=meter_id))
    else:
        form.meter_name.data = meter.meter_name
        form.sharing.data = meter.sharing
        form.api_key.data = meter.api_key
    return render_template(
        'meters/manage_meter.html',
        id=meter_id,
        meter_name=get_meter_name(meter_id),
        form=form)


@meters.route('/<int:meter_id>/manage/import', methods=["GET", "POST"])
@login_required
def manage_import(meter_id):
    """ Import meter data """
    if not meter_editable(meter_id):
        msg = 'Not authorised to manage this meter.'
        flash(msg, category='warning')
        return redirect(url_for('meters.index'))

    form = FileForm()
    if form.validate_on_submit():
        filename = secure_filename(str(meter_id) + '.csv')
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        form.upload_file.data.save(file_path)

        nmi = get_meter_name(meter_id)
        load_nem_data(meter_id, nmi, file_path)
        flash('Readings added', category='success')

        return redirect(url_for('meters.manage_import', meter_id=meter_id))
    return render_template(
        'meters/manage_import.html',
        id=meter_id,
        meter_name=get_meter_name(meter_id),
        form=form)


@meters.route('/<int:meter_id>/manage/export', methods=["GET", "POST"])
@login_required
def manage_export(meter_id):
    """ Manage meter data """
    if not meter_editable(meter_id):
        msg = 'Not authorised to manage this meter.'
        flash(msg, category='warning')
        return redirect(url_for('meters.index'))

    form = FlaskForm()
    if form.validate_on_submit():
        delete_meter_data(meter_id)
        msg = 'Meter deleted!'
        flash(msg, category='success')
        return redirect(url_for('meters.index'))

    return render_template(
        'meters/manage_export.html',
        id=meter_id,
        meter_name=get_meter_name(meter_id),
        form=form)


@meters.route('/<int:meter_id>/usage/')
def usage_redirect(meter_id):
    """ Redirect to latest available day """

    if not meter_visible(meter_id):
        return 'Not authorised to view this page', 403

    # Get meter details
    first_record, last_record, num_days = get_meter_stats(meter_id)
    if num_days < 1:
        flash(
            'No data! Upload some data before you can chart usage.',
            category='warning')
        return redirect(url_for('meters.manage_import', meter_id=meter_id))

    # Redirect to most recent month with data available
    return redirect(
        url_for(
            'meters.usage_monthly',
            meter_id=meter_id,
            year=last_record.year,
            month=last_record.month))


@meters.route('/<int:meter_id>/usage/<int:year>/<int:month>/<int:day>/')
def usage_daily(meter_id, year, month, day):
    """ Get daily usage stats """

    if not meter_visible(meter_id):
        return 'Not authorised to view this page', 403

    # Get meter details
    first_record, last_record, num_days = get_meter_stats(meter_id)
    if num_days == 0:
        msg = 'You need to upload some data before you can chart usage.'
        flash(msg, category='warning')
        return redirect(url_for('meters.manage_import', meter_id=meter_id))

    # Get start and end of the reporting period
    rpt_start = datetime(year, month, day)
    rpt_end = rpt_start + timedelta(days=1)

    # Get next/prev periods for navigation
    prev_day = rpt_start - timedelta(days=1)
    if prev_day < first_record:
        prev_day = None
    next_day = rpt_start + timedelta(days=1)
    if next_day > last_record:
        next_day = None

    return render_template(
        'meters/usage_day.html',
        meter_id=meter_id,
        meter_name=get_meter_name(meter_id),
        report_period='day',
        rpt_start=rpt_start,
        period_desc=rpt_start.strftime("%a %d %b %y"),
        start_date=rpt_start.strftime("%Y-%m-%d"),
        end_date=rpt_end.strftime("%Y-%m-%d"),
        prev_day=prev_day,
        next_day=next_day)


@meters.route('/<int:meter_id>/<start>/<end>/energy_data.json')
def energy_data(meter_id, start, end):
    if not meter_visible(meter_id):
        return 'Not authorised to view this page', 403

    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")

    chartdata = dict()

    # Add general consumption
    load_data = []
    reads = list(
        get_load_energy_readings(
            meter_id, start_dt, end_dt, channels=LOAD_CHS))
    split_reads = group_into_profiled_intervals(reads, interval_m=5)
    for read in split_reads:
        read_ts = pytz.utc.localize(read.end).timestamp() * 1000
        load_data.append((read_ts, read.usage/(5/60)))
    chartdata['consumption'] = {
        'label': 'General',
        'color': '#FFA500',
        'data': load_data
    }

    # Controlled load
    load_data = []
    reads = list(
        get_load_energy_readings(
            meter_id, start_dt, end_dt, channels=CONTROL_CHS))
    split_reads = group_into_profiled_intervals(reads, interval_m=5)
    for read in split_reads:
        if read.usage:
            read_ts = pytz.utc.localize(read.end).timestamp() * 1000
            load_data.append((read_ts, read.usage/(5/60)))
    chartdata['controlled'] = {
        'label': 'Controlled Load',
        'color': '#FAB57F',
        'data': load_data
    }

    # Add generation
    load_data = []
    reads = list(
        get_load_energy_readings(
            meter_id, start_dt, end_dt, channels=GENERATION_CHS))
    split_reads = group_into_profiled_intervals(reads, interval_m=5)
    for read in split_reads:
        read_ts = pytz.utc.localize(read.end).timestamp() * 1000
        load_data.append((read_ts, -read.usage/(5/60)))
    chartdata['generation'] = {
        'label': 'Generation',
        'color': '#006400',
        'data': load_data
    }

    return jsonify(chartdata)


@meters.route('/<int:meter_id>/usage/<int:year>/<int:month>/day_summary.json')
def month_day_data(meter_id, year, month):
    if not meter_visible(meter_id):
        return 'Not authorised to view this page', 403

    # Get start and end of the reporting period
    rpt_start = datetime(year, month, 1)
    rpt_end = rpt_start + relativedelta(months=1)
    rpt_end -= timedelta(days=1)  # Remove last day

    day_data = []
    load_data = []
    control_data = []
    generation_data = []
    for daily in get_daily_energy_readings(meter_id, rpt_start, rpt_end):

        day_url = url_for(
            'meters.usage_daily',
            meter_id=meter_id,
            year=daily.day.year,
            month=daily.day.month,
            day=daily.day.day)
        day_data.append({
            'day': daily.day.strftime("%Y-%m-%d"),
            'day_url': day_url,
            'load_total': daily.load_total,
            'control_total': daily.control_total,
            'export_total': daily.export_total
        })
        day_end = daily.day + timedelta(days=1)
        day_ts = pytz.utc.localize(day_end).timestamp() * 1000
        load_data.append((day_ts, daily.load_total))
        if daily.control_total:
            control_data.append((day_ts, daily.control_total))
        generation_data.append((day_ts, daily.export_total))

    consumption = {
        'label': "General",
        'color': '#FFA500',
        'data': load_data,
    }
    controlled = {
        'label': 'Controlled Load',
        'color': '#FAB57F',
        'data': control_data,
    }
    generation = {
        'label': 'Generation',
        'color': '#006400',
        'data': generation_data,
    }
    json_data = {'dailies': day_data, 'consumption': consumption, 'controlled': controlled, 'generation': generation}
    return jsonify(json_data)


@meters.route('/<int:meter_id>/usage/month_summary.json')
def monthly_data(meter_id):
    """ Return json object for flot chart
    """

    start, end = get_data_range(meter_id)

    load_data = []
    for year, month, _ in get_month_ranges(start, end):

        day_dt = datetime(year, month, 1)
        day_ts = pytz.utc.localize(day_dt).timestamp() * 1000
        mth = get_monthly_energy_readings(meter_id, year, month)
        daily_load = mth.load_total / mth.num_days
        load_data.append((day_ts, daily_load))

    consumption = {
        'label': "General",
        'color': '#FFA500',
        'data': load_data,
    }
    json_data = {'consumption': consumption}
    return jsonify(json_data)


@meters.route('/<int:meter_id>/usage/<int:year>/<int:month>/')
def usage_monthly(meter_id, year, month):
    """ Get monthly usage details """

    if not meter_visible(meter_id):
        return 'Not authorised to view this page', 403

    # Get meter details
    first_record, last_record, num_days = get_meter_stats(meter_id)
    if num_days < 1:
        flash(
            'You need to upload some data before you can chart usage.',
            category='warning')
        return redirect(url_for('meters.manage_import', meter_id=meter_id))

    # Get start and end of the reporting period
    rpt_start = datetime(year, month, 1)
    rpt_end = rpt_start + relativedelta(months=1)

    # Get next/prev periods for navigation
    prev_month = rpt_start - relativedelta(months=1)
    if prev_month < first_record:
        prev_month = None
    next_month = rpt_start + relativedelta(months=1)
    if next_month > last_record:
        next_month = None

    mth = monthly_bill_data(meter_id, rpt_start.year, rpt_start.month)

    daily_reads = get_daily_energy_readings(meter_id, rpt_start, rpt_end)

    return render_template(
        'meters/usage_month.html',
        meter_id=meter_id,
        meter_name=get_meter_name(meter_id),
        report_period='month',
        report_date=rpt_start.strftime("%Y-%m-%d"),
        period_desc=rpt_start.strftime("%b %y"),
        start_date=rpt_start.strftime("%Y-%m-%d"),
        end_date=rpt_end.strftime("%Y-%m-%d"),
        mth=mth,
        daily_reads=daily_reads,
        prev_month=prev_month,
        next_month=next_month)


def get_meter_stats(
        meter_id: int) -> Tuple[Optional[datetime], Optional[datetime], int]:
    """ Get the date range meter data exists for
    """
    first_record, last_record = get_data_range(meter_id)
    if not last_record:
        # No data
        return first_record, last_record, 0
    num_days = (last_record - first_record).days
    if num_days < 1:
        num_days = (last_record - first_record).seconds * 60 * 60 * 24
    return first_record, last_record, num_days
