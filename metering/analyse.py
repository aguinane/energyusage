"""
    metering.loader
    ~~~~~~~~~
    Define the meter data models
"""

import logging
from datetime import datetime, timedelta
from typing import List, Tuple
from statistics import mean
from dateutil.relativedelta import relativedelta
from qldtariffs import get_daily_usages
from qldtariffs import financial_year_starting
from sqlalchemy.orm import sessionmaker
from . import get_db_engine
from . import get_data_range
from . import get_load_energy_readings
from . import get_daily_energy_readings
from . import update_daily_total
from . import update_monthly_total


def refresh_daily_stats(meter_id):
    """ Update the daily totals after loading new readings """

    logging.info('Calculating daily stats for meter %s', meter_id)
    engine = get_db_engine(meter_id)
    Session = sessionmaker(bind=engine)
    session = Session()

    start, end = get_data_range(meter_id)
    records = list(get_load_energy_readings(meter_id, start, end))
    daily_ergon = list(get_daily_usages(
        records, retailer='ergon', tariff='t12'))
    daily_seq = list(get_daily_usages(records, retailer='agl', tariff='t12'))
    for i, day_ergon in enumerate(daily_ergon):
        update_daily_total(session, day_ergon.day,
                           day_ergon.total, 0, 0,
                           day_ergon.peak, day_ergon.shoulder,
                           daily_seq[i].peak, daily_seq[i].shoulder)
    session.commit()


def refresh_monthly_stats(meter_id):
    """ Update the daily totals after loading new readings """

    logging.info('Calculating monthly stats for meter %s', meter_id)
    engine = get_db_engine(meter_id)
    Session = sessionmaker(bind=engine)
    session = Session()

    start, end = get_data_range(meter_id)
    for year, month, _ in get_month_ranges(start, end):
        month_start = datetime(year, month, 1)
        month_end = month_start + relativedelta(months=1) - timedelta(days=1)
        num_days = month_end.day
        daily_totals = list(get_daily_energy_readings(
            meter_id, month_start, month_end))

        days = 0
        load_total = 0
        control_total = 0
        export_total = 0
        load_peak1 = 0
        load_shoulder1 = 0
        load_peak2 = 0
        load_shoulder2 = 0
        demands = []

        for day in daily_totals:
            days += 1
            load_total += day.load_total
            control_total += day.control_total
            export_total += day.export_total
            load_peak1 += day.load_peak1
            load_shoulder1 += day.load_shoulder1
            if day.load_peak1:
                demands.append(day.load_peak1)
            else:
                demands.append(day.load_shoulder1)
            load_peak2 += day.load_peak2
            load_shoulder2 += day.load_shoulder2

        top_4 = sorted(demands, reverse=True)[0:4]
        top_4_avg = mean(top_4)
        demand = average_daily_peak_demand(top_4_avg)

        unique = set(demands) 
        if len(unique) < 5:
            # Demand not variable enough, multiple demand by 2 to compensate
            # Readings are probably not interval readings
            demand = demand * 2

        update_monthly_total(session, year, month, num_days,
                             load_total, control_total, export_total,
                             demand, load_peak1, load_shoulder1,
                             load_peak2, load_shoulder2)

        session.commit()


def average_daily_peak_demand(peak_usage_kWh):
    """ Calculate the average daily peak demand in kW
    """
    peak_ratio = 1/6.5  # Peak period is 6.5 hrs
    return peak_usage_kWh * peak_ratio


def get_month_ranges(start: datetime, end: datetime) -> List[Tuple[int, int]]:
    """ Get billing months in time range """
    periods: list = []
    day = start
    while day <= end:
        fy = financial_year_starting(day)
        period = (day.year, day.month, fy)
        if period not in periods:
            periods.append(period)
        day += timedelta(days=1)
    return sorted(periods)
