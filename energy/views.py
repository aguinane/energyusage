import os
import uuid
import datetime

import arrow
from statistics import mean
from flask import render_template, url_for, jsonify, redirect, flash, request, Response
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from werkzeug.utils import secure_filename
import sqlalchemy
from qldtariffs import get_daily_charges, get_monthly_charges
from qldtariffs import electricity_charges_general
from qldtariffs import electricity_charges_tou
from qldtariffs import electricity_charges_tou_demand
from metering import load_nem_data
from metering import get_data_range, get_month_ranges
from metering import get_daily_energy_readings
from . import app, db
from .models import User, Meter, delete_meter_data
from .models import get_meter_name
from .models import get_user_meters, get_public_meters, visible_meters
from .forms import UsernamePasswordForm, FileForm, NewMeter, MeterDetails
from .charts import get_daily_chart_data, get_monthly_chart_data
from .charts import get_interval_chart_data
from .charts import monthly_bill_data
from .usage import average_daily_peak_demand


def get_user_details():
    """ Get details of loggged in user """

    try:
        current_username = current_user.username
    except AttributeError:
        return None, None

    user = User.query.filter_by(username=current_user.username).first()
    return user.user_id, user.username


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/meters')
def meters():
    user_id, _ = get_user_details()
    user_meters = list(get_user_meters(user_id))
    public_meters = list(get_public_meters())
    return render_template('meters.html',
                           user_meters=user_meters,
                           public_meters=public_meters)


@app.route('/new_meter', methods=["GET", "POST"])
@login_required
def new_meter():
    """ Form to create a new meter record """
    form = NewMeter()
    if form.validate_on_submit():
        user_id, user_name = get_user_details()
        if not user_id:
            flash('Something went wrong :/', category='error')
            return redirect(url_for('new_meter'))
        api_key = str(uuid.uuid4())
        meter = Meter(user_id=user_id,
                      meter_name=form.meter_name.data.upper().strip(),
                      sharing=form.sharing.data,
                      api_key=api_key)
        try:
            db.session.add(meter)
            db.session.commit()
            flash('New meter created!', category='success')
            return redirect(url_for('index'))
        except sqlalchemy.exc.IntegrityError:
            flash('Sorry, something went wrong :/', category='warning')
            return redirect(url_for('new_meter'))
    return render_template('new_meter.html', form=form)


def check_meter_permissions(user_id, meter_id):
    """ Return if user can see a meter """
    meter_id = int(meter_id)
    visible = False
    for meter, meter_name, user in visible_meters(user_id):
        if meter_id == meter:
            visible = True

    editable = False
    for meter, meter_name, user in get_user_meters(user_id):
        if meter_id == meter:
            editable = True

    return visible, editable


@app.route('/manage_meter/<int:meter_id>', methods=["GET", "POST"])
@login_required
def manage_meter(meter_id):
    """ Manage meter details """
    user_id, user_name = get_user_details()
    visible, editable = check_meter_permissions(user_id, meter_id)
    if not editable:
        msg = 'Not authorised to manage this meter.'
        flash(msg, category='warning')
        return redirect(url_for('meters'))

    meter = Meter.query.filter_by(meter_id=meter_id).first()
    form = MeterDetails()
    if form.validate_on_submit():
        meter.meter_name = form.meter_name.data.upper().strip()
        meter.sharing = form.sharing.data
        db.session.commit()
        flash('Meter updated', category='success')
        return redirect(url_for('manage_meter', meter_id=meter_id))
    else:
        form.meter_name.data = meter.meter_name
        form.sharing.data = meter.sharing
        form.api_key.data = meter.api_key
    return render_template('manage_meter.html', id=meter_id,
                           meter_name=get_meter_name(meter_id),
                           form=form)


@app.route('/manage_import/<int:meter_id>', methods=["GET", "POST"])
@login_required
def manage_import(meter_id):
    """ Import meter data """
    user_id, user_name = get_user_details()
    visible, editable = check_meter_permissions(user_id, meter_id)
    if not editable:
        msg = 'Not authorised to manage this meter.'
        flash(msg, category='warning')
        return redirect(url_for('meters'))

    form = FileForm()
    if form.validate_on_submit():
        filename = secure_filename(str(meter_id) + '.csv')
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        form.upload_file.data.save(file_path)

        nmi = get_meter_name(meter_id)
        load_nem_data(meter_id, nmi, file_path)
        flash('Readings added', category='success')

        return redirect(url_for('manage_import', meter_id=meter_id))
    return render_template('manage_import.html', id=meter_id,
                           meter_name=get_meter_name(meter_id),
                           form=form)


@app.route('/manage_export/<int:meter_id>', methods=["GET", "POST"])
@login_required
def manage_export(meter_id):
    """ Manage meter data """
    user_id, user_name = get_user_details()
    visible, editable = check_meter_permissions(user_id, meter_id)
    if not editable:
        msg = 'Not authorised to manage this meter.'
        flash(msg, category='warning')
        return redirect(url_for('meters'))

    form = FlaskForm()
    if form.validate_on_submit():
        delete_meter_data(meter_id)
        msg = 'Meter deleted!'
        flash(msg, category='success')
        return redirect(url_for('meters'))

    return render_template('manage_export.html', id=meter_id,
                           meter_name=get_meter_name(meter_id),
                           form=form)


@app.route('/export')
@login_required
def export_data():
    user_id, user_name = get_user_details()
    return Response(export_meter_data(user_id),
                    mimetype="text/csv",
                    headers={"Content-disposition":
                             "attachment; filename=data-export.csv"}
                    )


@app.route('/signup', methods=["GET", "POST"])
def signup():
    form = UsernamePasswordForm()
    if form.validate_on_submit():
        user = User(username=form.username.data.lower(),
                    password=form.password.data)
        try:
            db.session.add(user)
            db.session.commit()
            flash('User created!', category='success')
            return redirect(url_for('index'))
        except sqlalchemy.exc.IntegrityError:
            flash('Sorry, a user with that name already exists.', category='warning')
            return redirect(url_for('signup'))

    return render_template('signup.html', form=form)


@app.route('/signin', methods=["GET", "POST"])
def signin():
    form = UsernamePasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(
            username=form.username.data.lower()).first()
        if user is None:
            flash('No user called {} found!'.format(form.username.data.lower()),
                  category='danger')
            return redirect(url_for('signin'))
        if user.is_correct_password(form.password.data):
            login_user(user)
            return redirect(request.args.get('next') or url_for('index'))
        else:
            return redirect(url_for('signin'))
    return render_template('signin.html', form=form)


@app.route('/signout')
def signout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/meter/<int:meter_id>/month_usage/', methods=["GET", "POST"])
def usage_month(meter_id):
    """ Get monthly usage details """
    # Get user details
    user_id, user_name = get_user_details()
    visible, editable = check_meter_permissions(user_id, meter_id)
    if not visible:
        return 'Not authorised to view this page', 403

    # Get meter details
    first_record, last_record, num_days = get_meter_stats(meter_id)
    if num_days < 1:
        flash('You need to upload some data before you can chart usage.',
              category='warning')
        return redirect(url_for('manage_import', meter_id=meter_id))

    # Specify default month to report on
    try:
        report_date = request.values['report_date']
    except KeyError:
        report_date = '{}-{}-01'.format(str(last_record.year).zfill(2),
                                        str(last_record.month).zfill(2))
        return redirect(url_for('usage_month', meter_id=meter_id, report_date=report_date))

    rs = arrow.get(report_date)
    rs = arrow.get(rs.year, rs.month, 1)  # Make sure start of month
    re = rs.replace(months=+1)
    if rs < first_record:
        rs = first_record
    if re > last_record:
        re = last_record
    period_desc = rs.format('MMM YY')
    period_nav = get_navigation_range('month', rs, first_record, last_record)

    plot_settings = calculate_plot_settings(report_period='month')
    mth = monthly_bill_data(meter_id, rs.year, rs.month)
    return render_template('usage_month.html', meter_id=meter_id,
                           meter_name=get_meter_name(meter_id),
                           report_period='month', report_date=report_date,
                           period_desc=period_desc,
                           period_nav=period_nav,
                           plot_settings=plot_settings,
                           start_date=rs.format('YYYY-MM-DD'),
                           end_date=re.format('YYYY-MM-DD'),
                           mth=mth
                           )


@app.route('/meter/<int:meter_id>/<int:year>/<int:month>/monthly.json')
@login_required
def monthly_bill(meter_id: int, year: int, month: int):
    # Get user details
    user_id, user_name = get_user_details()
    visible, editable = check_meter_permissions(user_id, meter_id)
    if not visible:
        return 'Not authorised to view this page', 403

    """ Return the monthly bill costs as json """
    month_bill = monthly_bill_data(meter_id, year, month)
    return jsonify(month_bill)



@app.route('/meter/<int:meter_id>/all_usage/', methods=["GET", "POST"])
def usage_all(meter_id: int):
    """ Show billing for all months """
    # Get user details
    user_id, user_name = get_user_details()
    visible, editable = check_meter_permissions(user_id, meter_id)
    if not visible:
        return 'Not authorised to view this page', 403

    # Get meter details
    first_record, last_record, num_days = get_meter_stats(meter_id)
    if num_days < 1:
        flash('You need to upload some data before you can chart usage.',
              category='warning')
        return redirect(url_for('manage_import', id=meter_id))

    rs = arrow.get(first_record)
    re = arrow.get(last_record)
    num_days = (re - rs).days

    plot_settings = calculate_plot_settings(report_period='all')

    start, end = get_data_range(meter_id)
    billing_months =  get_month_ranges(start, end)
    fys = sorted(set([mth[2] for mth in billing_months]), reverse=True)

    return render_template('usage_all.html', meter_id=meter_id,
                           meter_name=get_meter_name(meter_id),
                           plot_settings=plot_settings,
                           start_date=rs.format('YYYY-MM-DD'),
                           end_date=re.format('YYYY-MM-DD'),
                           billing_months=billing_months, fys=fys
                           )


def get_billing_months(start_date, end_date):
    """ Return list of billing months """
    for i in range(start_date.year, end_date.year+1):
        if start_date.year == end_date.year:
            start_month = start_date.month
            stop_month = end_date.month
        elif i == start_date.year:
            start_month = start_date.month
            stop_month = 12
        elif i == end_date.year:
            start_month = 1
            stop_month = end_date.month - 1
        else:
            start_month = 1
            stop_month = 12

        for j in range(start_month, stop_month+1):
            month_start = datetime.datetime(i, j, 1)
            month_start = arrow.get(month_start).format('YYYY-MM-DD')
            month_desc = arrow.get(month_start).format('MMM YY')
            yield month_start, month_desc


@app.route('/meter/<int:meter_id>/day_usage/', methods=["GET", "POST"])
def usage_day(meter_id):
    """ Get daily usage stats """
    # Get user details
    user_id, user_name = get_user_details()

    visible, editable = check_meter_permissions(user_id, meter_id)
    if not visible:
        return 'Not authorised to view this page', 403

    # Get meter details
    first_record, last_record, num_days = get_meter_stats(meter_id)
    if num_days == 0:
        flash('You need to upload some data before you can chart usage.',
              category='warning')
        return redirect(url_for('manage_import', id=meter_id))

    # Specify default day to report on
    try:
        report_date = request.values['report_date']
    except KeyError:
        report_date = '{}-{}-{}'.format(str(last_record.year).zfill(2),
                                        str(last_record.month).zfill(2),
                                        str(last_record.day).zfill(2))
        return redirect(url_for('usage_day', meter_id=meter_id, report_date=report_date))

    # Get end of reporting period
    # And next and previous periods
    rs = arrow.get(report_date)
    re = rs.replace(days=+1)
    period_desc = rs.format('ddd DD MMM YY')
    period_nav = get_navigation_range('day', rs, first_record, last_record)
    plot_settings = calculate_plot_settings(report_period='day', interval=30)

    return render_template('usage_day.html', meter_id=meter_id,
                           meter_name=get_meter_name(meter_id),
                           report_period='day', report_date=report_date,
                           period_desc=period_desc,
                           period_nav=period_nav,
                           plot_settings=plot_settings,
                           start_date=rs.format('YYYY-MM-DD'),
                           end_date=re.format('YYYY-MM-DD')
                           )


@app.route('/energy_data/')
@app.route('/energy_data/<meter_id>.json', methods=['POST', 'GET'])
def energy_data(meter_id=None):
    user_id, user_name = get_user_details()
    visible, editable = check_meter_permissions(user_id, meter_id)
    if not visible:
        return 'Not authorised to view this page', 403
    if meter_id is None:
        return 'json chart api'
    else:
        params = request.args.to_dict()
        start_date = arrow.get(params['start_date']).datetime
        end_date = arrow.get(params['end_date']).datetime
        flotData = get_interval_chart_data(meter_id, start_date, end_date)
        return jsonify(flotData)



@app.route('/about/')
def about():
    return render_template('about.html')


@app.route('/daily_data/<meter_id>.json', methods=['POST', 'GET'])
def daily_data(meter_id):
    user_id, user_name = get_user_details()
    visible, editable = check_meter_permissions(user_id, meter_id)
    if not visible:
        return 'Not authorised to view this page', 403

    params = request.args.to_dict()
    start_date = arrow.get(params['start_date']).datetime
    end_date = arrow.get(params['end_date']).replace(days=-1).datetime
    flotData = get_daily_chart_data(meter_id, start_date, end_date)
    return jsonify(flotData)


@app.route('/monthly_data/<meter_id>.json', methods=['POST', 'GET'])
def monthly_data(meter_id):
    user_id, user_name = get_user_details()
    visible, editable = check_meter_permissions(user_id, meter_id)
    if not visible:
        return 'Not authorised to view this page', 403

    params = request.args.to_dict()
    start_date = arrow.get(params['start_date']).datetime
    end_date = arrow.get(params['end_date']).replace(days=-1).datetime
    flotData = get_monthly_chart_data(meter_id, start_date, end_date)
    return jsonify(flotData)


def get_meter_stats(meter_id):
    """ Get the date range meter data exists for
    """
    first_record, last_record = get_data_range(meter_id)
    first_record = arrow.get(first_record)
    last_record = arrow.get(last_record)
    num_days = (last_record - first_record).days
    if num_days < 1:
        num_days = (last_record - first_record).seconds * 60 * 60 * 24
    return first_record, last_record, num_days


def get_navigation_range(report_period, rs, first_record, last_record):
    """ Get the next period to report on (if data available)
    """
    if report_period == 'day':
        prev_date = rs.replace(days=-1)
        next_date = rs.replace(days=+1)
    else:
        prev_date = rs.replace(months=-1)
        next_date = rs.replace(months=+1)

    # Define valid navigation ranges
    if next_date >= last_record:
        next_date_enabled = False
    else:
        next_date_enabled = True

    if prev_date <= first_record:
        if report_period == 'month' and prev_date >= first_record.replace(months=-1):
            prev_date_enabled = True
        else:
            prev_date_enabled = False
    else:
        prev_date_enabled = True

    period_nav = {'prev_date': prev_date.format('YYYY-MM-DD'),
                  'prev_enabled': prev_date_enabled,
                  'next_date': next_date.format('YYYY-MM-DD'),
                  'next_enabled': next_date_enabled
                  }

    return period_nav


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
