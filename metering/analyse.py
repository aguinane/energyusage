"""
    metering.analyse
    ~~~~~~~~~
    Summarise stats up to daily and monthly totals
"""

import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from statistics import mean
from dateutil.relativedelta import relativedelta
from qldtariffs import get_daily_usages
from qldtariffs import financial_year_starting
from sqlalchemy.orm import sessionmaker
from . import get_db_engine
from . import Dailies
from . import get_data_range
from . import get_load_energy_readings
from . import get_daily_energy_readings
from . import update_daily_total
from . import update_daily_segments
from . import update_monthly_total

LOAD_CHS = ['E1', '11']
CONTROL_CHS = ['E2', '41']
GENERATION_CHS = ['B1', '71']


def refresh_daily_stats(meter_id: int,
                        start: Optional[datetime] = None,
                        end: Optional[datetime] = None):
    """ Update the daily totals after loading new readings """

    engine = get_db_engine(meter_id)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Get start and end of available data
    if not start or not end:
        start, end = get_data_range(meter_id)

    msg = f'Calculating daily stats for meter {meter_id}'
    msg += f' from {start.strftime("%Y%m%d")} to {end.strftime("%Y%m%d")}'
    logging.info(msg)

    # Get General Consumption Stats
    records = list(
        get_load_energy_readings(meter_id, start, end, channels=LOAD_CHS))
    daily_ergon = list(
        get_daily_usages(records, retailer='ergon', tariff='t12'))
    daily_seq = list(get_daily_usages(records, retailer='agl', tariff='t12'))

    # Get Controlled Load Stats
    records = list(
        get_load_energy_readings(meter_id, start, end, channels=CONTROL_CHS))
    daily_control = list(get_daily_usages(records))

    # Get Generation Stats
    records = list(
        get_load_energy_readings(
            meter_id, start, end, channels=GENERATION_CHS))
    daily_generation = list(get_daily_usages(records))

    for i, day_ergon in enumerate(daily_ergon):

        day = day_ergon.day
        load_total = day_ergon.total
        load_peak = day_ergon.peak
        load_shoulder = day_ergon.shoulder
        load_peak2 = daily_seq[i].peak
        load_shoulder2 = daily_seq[i].shoulder
        # See if Control and Generation Channels exist
        try:
            controlled_total = daily_control[i].total
        except IndexError:
            controlled_total = 0
        try:
            generation_total = daily_generation[i].total
        except IndexError:
            generation_total = 0

        update_daily_total(session, day, load_total, controlled_total,
                           generation_total, load_peak, load_shoulder,
                           load_peak2, load_shoulder2)
    session.commit()

    # Estimate values to complete the month
    next_month = datetime(end.year, end.month, 1) + relativedelta(months=1)
    est_day = end
    while est_day < next_month:
        # Update with estimate if not already populated
        r = session.query(Dailies).filter(Dailies.day == day).first()
        if r is None:
            update_daily_total(
                session,
                est_day,
                load_total,
                controlled_total,
                generation_total,
                load_peak,
                load_shoulder,
                load_peak2,
                load_shoulder2,
                estimated=True)
        est_day += timedelta(days=1)
    session.commit()


def refresh_daily_segments(meter_id: int,
                           start: Optional[datetime] = None,
                           end: Optional[datetime] = None):
    """ Update the daily totals after loading new readings """

    engine = get_db_engine(meter_id)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Get start and end of available data
    if not start or not end:
        start, end = get_data_range(meter_id)

    msg = f'Calculating daily segments for meter {meter_id}'
    msg += f' from {start.strftime("%Y%m%d")} to {end.strftime("%Y%m%d")}'
    logging.info(msg)

    # Get General Consumption Stats
    load_records = list(
        get_load_energy_readings(meter_id, start, end, channels=LOAD_CHS))

    day_summary = {}
    for read in load_records:
        read_start = read[0]
        day = read_start.date()

        if day not in day_summary.keys():
            day_seg = {
                'a': 0.0,
                'b': 0.0,
                'c': 0.0,
                'd': 0.0,
                'e': 0.0,
                'f': 0.0,
                'g': 0.0,
                'h': 0.0,
            }
            day_summary[day] = day_seg
        else:
            day_seg = day_summary[day]
        tod = get_time_of_day_segment(read_start).lower()
        val = read[2]
        day_summary[day][tod] += val

    for day in day_summary.keys():
        day_seg = day_summary[day]
        update_daily_segments(session, day, **day_seg)
    session.commit()


def get_time_of_day_segment(dt: datetime) -> str:
    """ Return day segment of datetime """
    if dt.hour < 3:
        return 'A'
    if dt.hour < 6:
        return 'B'
    if dt.hour < 9:
        return 'C'
    if dt.hour < 12:
        return 'D'
    if dt.hour < 15:
        return 'E'
    if dt.hour < 18:
        return 'F'
    if dt.hour < 21:
        return 'G'
    return 'H'


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
        daily_totals = list(
            get_daily_energy_readings(meter_id, month_start, month_end))

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

        update_monthly_total(session, year, month, num_days, load_total,
                             control_total, export_total, demand, load_peak1,
                             load_shoulder1, load_peak2, load_shoulder2)

        session.commit()


def average_daily_peak_demand(peak_usage_kWh):
    """ Calculate the average daily peak demand in kW
    """
    peak_ratio = 1 / 6.5  # Peak period is 6.5 hrs
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
