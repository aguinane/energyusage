from flask import render_template, url_for, jsonify, redirect, flash, request, Response
from flask_login import login_user, logout_user, login_required, current_user
import os
import arrow
from werkzeug.utils import secure_filename
from . import app, db
from .models import User, get_data_range
from .loader import import_meter_data, export_meter_data
from .forms import UsernamePasswordForm, FileForm
from .charts import get_energy_chart_data, get_daily_chart_data
from .tariff import GeneralSupplyTariff, TimeofUseTariff, DemandTariff
import sqlalchemy


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/manage', methods=["GET", "POST"])
@login_required
def manage():
    form = FileForm()
    if form.validate_on_submit():
        filename = secure_filename(current_user.username+'.csv')
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        form.upload_file.data.save(file_path)
        new, skipped, failed = import_meter_data(current_user.username, file_path)
        if new > 0:
            msg = '{} new readings added.'.format(new)
            flash(msg, category='success')
        else:
            msg = 'No new readings could be added. '
            flash(msg, category='warning')

        if skipped > 0:
            msg = '{} records already existed and were skipped.'.format(skipped)
            flash(msg, category='warning')

        if failed > 0:
            msg = '{} records were in the wrong format.'.format(failed)
            flash(msg, category='danger')

        return redirect(url_for('manage'))
    return render_template('manage.html', form=form)



@app.route('/export')
@login_required
def export_data():
    user_id = User.query.filter_by(username=current_user.username).first().id
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
        user = User.query.filter_by(username=form.username.data.lower()).first()
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


@app.route('/usage/')
@login_required
def usage():
    return redirect(url_for('usage_month'))


@app.route('/usage/day/', methods=["GET", "POST"])
@login_required
def usage_day():

    # Get user details
    user_id = User.query.filter_by(username=current_user.username).first().id
    first_record, last_record, num_days = get_user_stats(user_id)
    if num_days == 0:
        flash('You need to upload some data before you can chart usage.',
              category='warning')
        return redirect(url_for('manage'))

    # Specify default day to report on
    try:
        report_date = request.values['report_date']
    except KeyError:
        report_date = '{}-{}-{}'.format(last_record.year, last_record.month, last_record.day)
        return redirect(url_for('usage_day', report_date=report_date))

    # Get end of reporting period
    # And next and previous periods
    rs = arrow.get(report_date)
    re = rs.replace(days=+1)
    period_desc = rs.format('ddd DD MMM YY')
    period_nav = get_navigation_range('day', rs, first_record, last_record)

    t11, t12, t14 = calculate_usage_costs(user_id, rs, re)
    plot_settings = calculate_plot_settings(report_period='day')


    return render_template('usage_day.html', meter_id = user_id,
                           report_period = 'day', report_date=report_date,
                           t11=t11, t12=t12, t14=t14,
                           period_desc = period_desc,
                           period_nav = period_nav,
                           plot_settings=plot_settings,
                           start_date = rs.format('YYYY-MM-DD'),
                           end_date = re.format('YYYY-MM-DD')
                           )


@app.route('/usage/month/', methods=["GET", "POST"])
@login_required
def usage_month():

    # Get user details
    user_id = User.query.filter_by(username=current_user.username).first().id
    first_record, last_record, num_days = get_user_stats(user_id)
    if num_days < 1:
        flash('You need to upload some data before you can chart usage.',
              category='warning')
        return redirect(url_for('manage'))

    # Specify default month to report on
    try:
        report_date = request.values['report_date']
    except KeyError:
        report_date = '{}-{}-01'.format(last_record.year, last_record.month)
        return redirect(url_for('usage_month', report_date=report_date))

    # Get end of reporting period
    # And next and previous periods
    rs = arrow.get(report_date)
    rs = arrow.get(rs.year, rs.month, 1)  # Make sure start of month
    re = rs.replace(months=+1)
    period_nav = get_navigation_range('month', rs, first_record, last_record)
    if rs < first_record:
        rs = first_record
    if re > last_record:
        re = last_record
    num_days = (re - rs).days
    period_desc = rs.format('MMM YY')


    t11, t12, t14 = calculate_usage_costs(user_id, rs, re)
    plot_settings = calculate_plot_settings(report_period='month')


    return render_template('usage_month.html', meter_id = user_id,
                           report_period = 'month', report_date=report_date,
                           t11=t11, t12=t12, t14=t14,
                           period_desc = period_desc,
                           period_nav = period_nav, num_days=num_days,
                           plot_settings=plot_settings,
                           start_date = rs.format('YYYY-MM-DD'),
                           end_date = re.format('YYYY-MM-DD')
                           )


@app.route('/billing/', methods=["GET", "POST"])
@login_required
def billing():
    # Get user details
    user_id = User.query.filter_by(username=current_user.username).first().id
    first_record, last_record, num_days = get_user_stats(user_id)
    if num_days < 1:
        flash('You need to upload some data before you can chart usage.',
              category='warning')
        return redirect(url_for('manage'))

    # Specify default day to report on
    try:
        report_date = request.values['report_date']
    except KeyError:
        report_date = str(last_record.year) + '-' + str(last_record.month) + '-' + str(last_record.day)

    rs = arrow.get(first_record)
    re = arrow.get(last_record)
    num_days = (re - rs).days

    t11, t12, t14 = calculate_usage_costs(user_id, rs, re)
    plot_settings = calculate_plot_settings(report_period='month')


    return render_template('billing.html', meter_id = user_id,
                           report_date = report_date,
                           t11=t11, t12=t12, t14=t14,
                           plot_settings=plot_settings,
                           start_date = rs.format('YYYY-MM-DD'),
                           end_date = re.format('YYYY-MM-DD')
                           )


@app.route('/about/')
def about():
    return render_template('about.html')


@app.route('/energy_data/')
@app.route('/energy_data/<meter_id>.json', methods=['POST', 'GET'])
@login_required
def energy_data(meter_id=None):
    if meter_id is None:
        return 'json chart api'
    else:
        params = request.args.to_dict()
        start_date = arrow.get(params['start_date']).replace(minutes=+10).datetime
        end_date = arrow.get(params['end_date']).datetime
        flotData = get_energy_chart_data(meter_id, start_date, end_date)
        return jsonify(flotData)


@app.route('/daily_data/')
@app.route('/daily_data/<meter_id>.json', methods=['POST', 'GET'])
@login_required
def daily_data(meter_id=None):
    if meter_id is None:
        return 'json chart api'
    else:
        params = request.args.to_dict()
        start_date = arrow.get(params['start_date']).replace(minutes=+10).datetime
        end_date = arrow.get(params['end_date']).datetime
        flotData = get_daily_chart_data(meter_id, start_date, end_date)
        return jsonify(flotData)


def get_user_stats(user_id):
    """ Get the date range meter data exists for
    """
    first_record, last_record = get_data_range(user_id)
    first_record = arrow.get(first_record)
    last_record = arrow.get(last_record)
    num_days = (last_record - first_record).days
    if num_days < 1:
        num_days = (last_record - first_record).seconds * 60 * 60 * 24
    return first_record, last_record, num_days


def calculate_usage_costs(user_id, rs, re):
    """ Calculate usage costs
    """
    t11 = GeneralSupplyTariff(user_id)
    t11.calculate_bill(start_date=rs.datetime, end_date=re.datetime)

    t12 = TimeofUseTariff(user_id)
    t12.calculate_bill(start_date=rs.datetime, end_date=re.datetime)

    t14 = DemandTariff(user_id)
    t14.calculate_bill(start_date=rs.datetime, end_date=re.datetime)

    return t11, t12, t14


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
    if report_period == 'month':
        plot_settings['minTickSize'] = 'day'
    else:  # Day
        plot_settings['minTickSize'] = 'hour'
    return plot_settings
