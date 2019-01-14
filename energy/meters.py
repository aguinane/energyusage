"""
    energy.meter
    ~~~~~~~~~
    Module for routes relating to a specific meter
"""

import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from flask import Blueprint, render_template, redirect, url_for
from flask import request, flash, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from werkzeug.utils import secure_filename
import arrow
from metering import load_nem_data
from metering import get_data_range, get_month_ranges
from metering import get_daily_energy_readings

from . import app, db
from .views import get_user_details
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

    # Define chart settings
    plot_settings = calculate_plot_settings(report_period='day', interval=30)

    return render_template(
        'meters/usage_day.html',
        meter_id=meter_id,
        meter_name=get_meter_name(meter_id),
        report_period='day',
        rpt_start=rpt_start,
        period_desc=rpt_start.strftime("%a %d %b %y"),
        plot_settings=plot_settings,
        start_date=rpt_start.strftime("%Y-%m-%d"),
        end_date=rpt_end.strftime("%Y-%m-%d"),
        prev_day=prev_day,
        next_day=next_day)


@meters.route('/<int:meter_id>/usage/<int:year>/<int:month>/day_summary.json')
def month_day_data(meter_id, year, month):
    if not meter_visible(meter_id):
        return 'Not authorised to view this page', 403

    # Get start and end of the reporting period
    rpt_start = datetime(year, month, 1)
    rpt_end = rpt_start + relativedelta(months=1)
    rpt_end -= timedelta(days=1) # Remove last day

    day_data = []
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
            'timestamp': daily.day.timestamp(),
            'load_total': daily.load_total,
            'control_total': daily.control_total,
            'export_total': daily.export_total
        })
    return jsonify(day_data)


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

    # Define chart settings
    plot_settings = calculate_plot_settings(report_period='month')

    mth = monthly_bill_data(meter_id, rpt_start.year, rpt_start.month)

    daily_reads = get_daily_energy_readings(meter_id, rpt_start, rpt_end)
    print(daily_reads)

    return render_template(
        'meters/usage_month.html',
        meter_id=meter_id,
        meter_name=get_meter_name(meter_id),
        report_period='month',
        report_date=rpt_start.strftime("%Y-%m-%d"),
        period_desc=rpt_start.strftime("%b %y"),
        plot_settings=plot_settings,
        start_date=rpt_start.strftime("%Y-%m-%d"),
        end_date=rpt_end.strftime("%Y-%m-%d"),
        mth=mth,
        daily_reads=daily_reads,
        prev_month=prev_month,
        next_month=next_month)


def get_meter_stats(meter_id):
    """ Get the date range meter data exists for
    """
    first_record, last_record = get_data_range(meter_id)
    num_days = (last_record - first_record).days
    if num_days < 1:
        num_days = (last_record - first_record).seconds * 60 * 60 * 24
    return first_record, last_record, num_days


def calculate_plot_settings(report_period='day', interval=10):
    # Specify chart settings depending on report period
    plot_settings = dict()
    plot_settings['barWidth'] = 1000 * 60 * interval
    if report_period == 'all':
        plot_settings['minTickSize'] = 'month'
    elif report_period == 'month':
        plot_settings['minTickSize'] = 'day'
    else:  # Day
        plot_settings['minTickSize'] = 'hour'
    return plot_settings
