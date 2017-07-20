import arrow
from qldtariffs import get_daily_usages
from .usage import get_energy_data, get_power_data
from .usage import get_consumption_data, average_daily_peak_demand


def get_energy_chart_data(meter_id, start_date, end_date):
    """ Return json object for flot chart
    """
    chartdata = {}
    chartdata['label'] = 'Energy Profile'
    chartdata['consumption'] = []

    for r in get_energy_data(meter_id, start_date, end_date):
        dTime = arrow.get(r.reading_start)
        ts = int(dTime.timestamp * 1000)
        impWh = r.e1 / 1000
        chartdata['consumption'].append([ts, impWh])

    chartdata['power'] = []
    for r in get_power_data(meter_id, start_date, end_date):
        dTime = arrow.get(r[0])
        ts = int(dTime.timestamp * 1000)
        ts = ts - (1000 * 60 * 30)  # Offset 30 mins so steps line up properly on chart
        impW = r[1] / 1000
        chartdata['power'].append([ts, impW])

    # Finally add one more point to finish the step increment
    if ts:
        ts = ts + (1000 * 60 * 30)  # Offset 30 mins so steps line up properly on chart
        chartdata['power'].append([ts, impW])

    return chartdata


def get_daily_chart_data(meter_id, start_date, end_date):
    """ Return json object for flot chart
    """
    chartdata = {}
    chartdata['consumption'] = []
    chartdata['consumption_peak'] = []
    chartdata['consumption_offpeak'] = []
    chartdata['demand'] = []

    readings = list(get_consumption_data(meter_id, start_date, end_date))
    usage_data = get_daily_usages(readings, 'Ergon', 'T14')
    for day in usage_data:
        dTime = arrow.get(day).replace(days=+1)
        ts = int(dTime.timestamp * 1000)
        usage_total = usage_data[day].all
        usage_peak = usage_data[day].peak
        usage_offpeak = usage_data[day].offpeak
        demand = average_daily_peak_demand(usage_data[day].demand)
        chartdata['consumption'].append([ts, usage_total])
        chartdata['consumption_peak'].append([ts, usage_peak])
        chartdata['consumption_offpeak'].append([ts, usage_offpeak])
        chartdata['demand'].append([ts, demand])

    return chartdata
