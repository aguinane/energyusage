"""
    metering.loader
    ~~~~~~~~~
    Define the meter data models
"""

from nemreader import read_nem_file
from sqlalchemy.orm import sessionmaker
from energy_shaper import split_into_daily_intervals
from . import get_db_engine
from . import save_energy_reading
from . import refresh_daily_stats
from . import refresh_monthly_stats


def load_nem_data(meter_id, nmi, nem_file):
    """ Load data from NEM file and save to database """

    engine = get_db_engine(meter_id)
    Session = sessionmaker(bind=engine)
    session = Session()

    m = read_nem_file(nem_file)
    channels = m.readings[nmi]

    for ch_name in channels.keys():

        reads = split_into_daily_intervals(channels[ch_name])
        for read in reads:
            try:
                quality_method = read[3]
            except IndexError:
                quality_method = None
            save_energy_reading(session, ch_name,
                                read[0], read[1],
                                read[2], quality_method)
    session.commit()
    refresh_daily_stats(meter_id)
    refresh_monthly_stats(meter_id)
    