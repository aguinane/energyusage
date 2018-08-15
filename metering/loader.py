"""
    metering.loader
    ~~~~~~~~~
    Define the meter data models
"""

from nemreader import read_nem_file
from sqlalchemy.orm import sessionmaker
from . import get_db_engine
from . import save_energy_reading
from . import refresh_daily_stats


def load_nem_data(meter_id, nmi, nem_file):
    """ Load data from NEM file and save to database """

    engine = get_db_engine(meter_id)
    Session = sessionmaker(bind=engine)
    session = Session()

    m = read_nem_file(nem_file)
    channels = m.readings[nmi]

    for ch_name in channels.keys():
        for read in channels[ch_name]:

            save_energy_reading(session, ch_name,
                                read.t_start, read.t_end,
                                read.read_value, read.quality_method)
    session.commit()
    refresh_daily_stats(meter_id)
