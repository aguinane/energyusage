import datetime
import arrow
from .models import Energy


def average_daily_peak_demand(peak_usage_kWh):
    """ Calculate the average daily peak demand in kW
    """
    peak_ratio = 1/6.5  # Peak period is 6.5 hrs
    return peak_usage_kWh * peak_ratio


def get_power_data(meter_id, start_date, end_date):
    """ Get 30 min power data for a meter
    """
    power = {}
    for r in get_energy_data(meter_id, start_date, end_date):
        rd = arrow.get(r.reading_date)
        interval = r.interval
        imp = r.imp
        if not imp:  # If null
            imp = 0

        # Round up to nearest 30 min interval
        if rd.minute == 0:
            pass  # Nothing to do
        elif rd.minute > 30:
            rd = rd.replace(minute=0)
            rd = rd.replace(hours=+1)
        else:
            rd = rd.replace(minute=30)

        # Increment dictionary value
        if rd not in power:
            power[rd] = imp
        else:
            power[rd] += imp

    for key in sorted(power.keys()):
        impW = convert_wh_to_w(power[key], hours=0.5)
        yield (key, impW)


def get_consumption_data(meter_id, start_date, end_date):
    """ Get consumption data for a meter
    """
    for r in get_energy_data(meter_id, start_date, end_date):
        period_start = r.reading_date - datetime.timedelta(seconds=r.interval*60)
        period_end = r.reading_date
        usage_kWh = r.imp/1000
        yield (period_start, period_end, usage_kWh)


def get_energy_data(meter_id, start_date, end_date):
    """ Get energy data for a meter
    """
    readings = Energy.query.filter(Energy.user_id == meter_id)
    readings = readings.filter(Energy.reading_date >= start_date)
    readings = readings.filter(Energy.reading_date <= end_date).all()
    return readings


def convert_wh_to_w(Wh, hours=0.5):
    """ Find average W for the period, specified in hours
    """
    return Wh / hours


def convert_w_to_wh(W, hours=0.5):
    """ Find average W for the period, specified in hours
    """
    return W * hours
