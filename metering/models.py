"""
    metering.models
    ~~~~~~~~~
    Define the meter data models
"""

import os
from datetime import datetime, timedelta
from typing import Tuple
from sqlalchemy import create_engine
from sqlalchemy import func
from sqlalchemy import Column, String, DateTime, Float, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from energy_shaper import group_into_profiled_intervals

# Initialize the database
Base = declarative_base()


def get_db_engine(meter_id):
    """ Create database and return engine """
    db_name = f'meter_{meter_id}.db'
    db_dir = 'data'
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
    db_loc = os.path.join(db_dir, db_name)
    engine = create_engine(f'sqlite:///{db_loc}?check_same_thread=False')
    Base.metadata.create_all(engine)
    return engine


class Readings(Base):
    __tablename__ = 'readings'
    ch_name = Column(String, primary_key=True)
    read_start = Column(DateTime, primary_key=True)
    read_end = Column(DateTime, primary_key=True)
    read_value = Column(Float)
    quality_method = Column(String)


def get_data_range(meter_id) -> Tuple[datetime, datetime]:
    """ Get the minimum and maximum date ranges with data
    """
    engine = get_db_engine(meter_id)
    Session = sessionmaker(bind=engine)
    session = Session()

    min_date = session.query(func.min(Readings.read_start)).scalar()
    max_date = session.query(func.max(Readings.read_end)).scalar()
    return min_date, max_date


def save_energy_reading(session, ch_name,
                        read_start: datetime, read_end: datetime,
                        read_value, quality_method):
    """ Save reading to database """

    # Check existing records
    r = session.query(Readings).filter(Readings.ch_name == ch_name,
                                       Readings.read_start == read_start,
                                       Readings.read_end == read_end,
                                       ).first()
    if r is not None:
        return False

    read = Readings(ch_name=ch_name, read_start=read_start,
                    read_end=read_end, read_value=read_value,
                    quality_method=quality_method)
    session.add(read)


def get_load_energy_readings(meter_id, read_start: datetime, read_end: datetime):
    """ Get energy readings """

    engine = get_db_engine(meter_id)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Filter existing records
    res = session.query(Readings).filter(
        Readings.ch_name.in_(['E1', '11']),
        Readings.read_start >= read_start,
        Readings.read_end <= read_end,
    ).all()
    readings = []
    for r in res:
        readings.append((r.read_start, r.read_end, r.read_value))

    return group_into_profiled_intervals(readings, interval_m=5)


class Dailies(Base):
    __tablename__ = 'daily_totals'

    day = Column(DateTime, primary_key=True)
    # Channel Totals
    load_total = Column(Float)
    control_total = Column(Float)
    export_total = Column(Float)
    # Regional Peak Times
    load_peak1 = Column(Float)
    load_shoulder1 = Column(Float)
    # SEQ Peak Times
    load_peak2 = Column(Float)
    load_shoulder2 = Column(Float)


def get_daily_energy_readings(meter_id, read_start: datetime, read_end: datetime):
    """ Get energy readings """

    engine = get_db_engine(meter_id)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Filter existing records
    res = session.query(Dailies).filter(
        Dailies.day >= read_start,
        Dailies.day <= read_end,
    ).all()
    return res


def update_daily_total(session, day,
                       load_total, control_total, export_total,
                       load_peak1, load_shoulder1,
                       load_peak2, load_shoulder2
                       ):
    """ Save reading to database """

    # Check existing records
    r = session.query(Dailies).filter(Dailies.day == day).first()
    if r is None:
        daily = Dailies(day=day, load_total=load_total,
                        control_total=control_total, export_total=export_total,
                        load_peak1=load_peak1, load_shoulder1=load_shoulder1,
                        load_peak2=load_peak2, load_shoulder2=load_shoulder2)
        session.add(daily)
    else:
        r.load_total = load_total
        r.control_total = control_total
        r.export_total = export_total
        r.load_peak1 = load_peak1
        r.load_shoulder1 = load_shoulder1
        r.load_peak2 = load_peak2
        r.load_shoulder2 = load_shoulder2


class Monthlies(Base):
    __tablename__ = 'monthly_totals'

    year = Column(Integer, primary_key=True)
    month = Column(Integer, primary_key=True)
    num_days = Column(Integer)
    # Channel Totals
    load_total = Column(Float)
    control_total = Column(Float)
    export_total = Column(Float)
    # Regional Peak Times
    demand = Column(Float)
    load_peak1 = Column(Float)
    load_shoulder1 = Column(Float)
    # SEQ Peak Times
    load_peak2 = Column(Float)
    load_shoulder2 = Column(Float)


def get_monthly_energy_readings(meter_id, year: int, month: int):
    """ Get energy readings """

    engine = get_db_engine(meter_id)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Filter existing records
    res = session.query(Monthlies).filter(
        Monthlies.year == year,
        Monthlies.month <= month,
    ).all()
    return res


def update_monthly_total(session, year, month, num_days,
                         load_total, control_total, export_total,
                         demand, load_peak1, load_shoulder1,
                         load_peak2, load_shoulder2
                         ):
    """ Save reading to database """

    # Check existing records
    r = session.query(Monthlies).filter(Monthlies.year == year, 
                                        Monthlies.month == month).first()
    if r is None:
        monthly = Monthlies(year=year, month=month, num_days=num_days, 
                        load_total=load_total, control_total=control_total, 
                        export_total=export_total, demand=demand,
                        load_peak1=load_peak1, load_shoulder1=load_shoulder1,
                        load_peak2=load_peak2, load_shoulder2=load_shoulder2)
        session.add(monthly)
    else:
        r.load_total = load_total
        r.control_total = control_total
        r.export_total = export_total
        r.demand = demand
        r.load_peak1 = load_peak1
        r.load_shoulder1 = load_shoulder1
        r.load_peak2 = load_peak2
        r.load_shoulder2 = load_shoulder2
