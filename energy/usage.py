import datetime
import arrow
from .models import Energy
from qldtariffs import split_into_billing_intervals

def average_daily_peak_demand(peak_usage_kWh):
    """ Calculate the average daily peak demand in kW
    """
    peak_ratio = 1/6.5  # Peak period is 6.5 hrs
    return peak_usage_kWh * peak_ratio


def get_power_data(meter_id, start_date, end_date):
    """ Get 30 min power data for a meter
    """
    readings = []
    for reading in get_energy_data(meter_id, start_date, end_date):
        readings.append((reading.reading_start, reading.reading_end, reading.value))
    return split_into_billing_intervals(readings)


def get_consumption_data(meter_id, start_date, end_date):
    """ Get consumption data for a meter
    """
    for r in get_energy_data(meter_id, start_date, end_date, 'E1'):
        period_start = r.reading_start
        period_end = r.reading_end
        usage_kWh = r.value/1000
        yield (period_start, period_end, usage_kWh)


def get_energy_data(meter_id, start_date, end_date, meter_channel='E1'):
    """ Get energy data for a meter
    """
    readings = Energy.query.filter(Energy.meter_id == meter_id)
    readings = readings.filter(Energy.meter_channel == meter_channel)
    readings = readings.filter(Energy.reading_start >= start_date)
    readings = readings.filter(Energy.reading_end <= end_date).all()
    return readings


def convert_wh_to_w(Wh, hours=0.5):
    """ Find average W for the period, specified in hours
    """
    return Wh / hours


def convert_w_to_wh(W, hours=0.5):
    """ Find average W for the period, specified in hours
    """
    return W * hours
