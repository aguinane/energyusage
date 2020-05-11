import datetime
import arrow
from energy_shaper import group_into_profiled_intervals
from metering import get_load_energy_readings


def average_daily_peak_demand(peak_usage_kWh):
    """ Calculate the average daily peak demand in kW
    """
    peak_ratio = 1 / 6.5  # Peak period is 6.5 hrs
    return peak_usage_kWh * peak_ratio


def convert_wh_to_w(Wh, hours=0.5):
    """ Find average W for the period, specified in hours
    """
    return Wh / hours


def convert_w_to_wh(W, hours=0.5):
    """ Find average W for the period, specified in hours
    """
    return W * hours
