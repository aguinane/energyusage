import arrow
from metering import get_daily_energy_readings
from .usage import average_daily_peak_demand



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
