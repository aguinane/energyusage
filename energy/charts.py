import arrow
from datetime import datetime
from metering import get_daily_energy_readings
from metering import get_monthly_energy_readings
from metering import get_data_range, get_month_ranges
from qldtariffs import financial_year_starting
from qldtariffs import get_daily_charges, get_monthly_charges
from qldtariffs import electricity_charges_general
from qldtariffs import electricity_charges_tou
from qldtariffs import electricity_charges_tou_demand
from .usage import average_daily_peak_demand


def monthly_bill_data(meter_id: int, year: int, month: int):
    """ Get billing data for a given month """

    month_start = datetime(year, month, 1)
    period_desc = month_start.strftime('%Y %b')
    fy = str(financial_year_starting(month_start))

    mth = get_monthly_energy_readings(meter_id, year, month)
    offpeak1 = mth.load_total - mth.load_peak1
    offpeak2 = mth.load_total - mth.load_peak2 - mth.load_shoulder2
    t11 = electricity_charges_general('ergon', mth.num_days, mth.load_total, fy)
    t12 = electricity_charges_tou(
        'ergon', mth.num_days, mth.load_peak1, 0, offpeak1, fy)
    if month in [12, 1, 2]:
        peak_month = True
    else:
        peak_month = False
    t14 = electricity_charges_tou_demand(
        'ergon', mth.num_days, mth.load_total, mth.demand, fy, peak_month)

    agl_t11 = electricity_charges_general('agl', mth.num_days, mth.load_total, fy)
    agl_t12 = electricity_charges_tou(
        'agl', mth.num_days, mth.load_peak2, mth.load_shoulder2, offpeak2, fy)
    origin_t11 = electricity_charges_general('origin', mth.num_days, mth.load_total, fy)
    origin_t12 = electricity_charges_tou(
        'origin', mth.num_days, mth.load_peak2, mth.load_shoulder2, offpeak2, fy)

    return {'year': year, 'month': month, 'period_desc': period_desc,
            'num_days': mth.num_days, 'peak_month': peak_month,
            'load_total': mth.load_total, 'control_total': mth.control_total,
            'export_total': mth.export_total, 
            'load_peak1': mth.load_peak1,
            'load_shoulder1': 0,
            'load_offpeak1': offpeak1,
            'load_peak2': mth.load_peak2,
            'load_shoulder2': mth.load_shoulder2,
            'load_offpeak2': offpeak2,
            'demand': mth.demand,
            'ergon_t11': t11, 'ergon_t12': t12, 'ergon_t14': t14,
            'agl_t11': agl_t11, 'agl_t12': agl_t12,
            'origin_t11': origin_t11, 'origin_t12': origin_t12,
            }


def get_daily_chart_data(meter_id, start_date, end_date):
    """ Return json object for flot chart
    """
    chartdata = {}
    chartdata['consumption'] = []
    chartdata['consumption_peak'] = []
    chartdata['consumption_offpeak'] = []
    chartdata['demand'] = []

    daily_usages = get_daily_energy_readings(meter_id, start_date, end_date)
    for day in daily_usages:

        dTime = arrow.get(day.day).replace(days=+1)
        ts = int(dTime.timestamp * 1000)
        usage_total = day.load_total
        usage_peak = day.load_peak1
        usage_shoulder = day.load_shoulder1
        usage_offpeak = day.load_total - day.load_peak1
        if usage_peak:
            demand = average_daily_peak_demand(usage_peak)
        else:
            demand = average_daily_peak_demand(usage_shoulder)
        chartdata['consumption'].append([ts, usage_total])
        chartdata['consumption_peak'].append([ts, usage_peak])
        chartdata['consumption_offpeak'].append([ts, usage_offpeak])
        chartdata['demand'].append([ts, demand])

    return chartdata


def get_monthly_chart_data(meter_id, start_date, end_date):
    """ Return json object for flot chart
    """
    chartdata = {}
    chartdata['consumption'] = []
    chartdata['consumption_peak'] = []
    chartdata['consumption_offpeak'] = []
    chartdata['demand'] = []

    start, end = get_data_range(meter_id)
    
    for year, month in get_month_ranges(start, end):

        mth = get_monthly_energy_readings(meter_id, year, month)
        dTime = arrow.get(datetime(year, month, 1))
        ts = int(dTime.timestamp * 1000)
        usage_total = mth.load_total
        usage_peak = mth.load_peak1

        chartdata['consumption'].append([ts, usage_total])
        chartdata['consumption_peak'].append([ts, usage_peak])

    return chartdata
