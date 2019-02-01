"""
    metering.stats
    ~~~~~~~~~
    Get stats
"""

import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from statistics import mean
from dateutil.relativedelta import relativedelta
from qldtariffs import get_daily_usages
from qldtariffs import financial_year_starting
from sqlalchemy.orm import sessionmaker
from calendar import day_abbr

from . import Dailies
from . import get_daily_energy_readings

LOAD_CHS = ['E1', '11']
CONTROL_CHS = ['E2', '41']
GENERATION_CHS = ['B1', '71']


def get_day_of_week_avg(meter_id, start, end):

    print('Test')
    weekdays = {0: [], 1: [], 2: [], 3: [], 4: [], 5: [], 6: []}
    days = get_daily_energy_readings(meter_id, start, end)
    for day in days:
        if day.load_total:
            if not day.estimated:
                weekdays[day.day.weekday()].append(day.load_total)

    weekday_avgs = {}

    for day in weekdays.keys():
        weekday_avgs[day_abbr[day]] = mean(weekdays[day])

        weekday_avgs['weekends'] = mean(weekdays[6] + weekdays[5])
        weekday_avgs['weekdays'] = mean(weekdays[0] + weekdays[1] +
                                        weekdays[2] + weekdays[3] +
                                        weekdays[4])
    return weekday_avgs
