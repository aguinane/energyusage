"""
    metering.loader
    ~~~~~~~~~
    Define the meter data models
"""

import logging
from nemreader import read_nem_file
from sqlalchemy.orm import sessionmaker
from energy_shaper import split_into_daily_intervals
from . import get_db_engine
from . import save_energy_reading
from . import refresh_daily_stats
from . import refresh_monthly_stats


def load_nem_data(meter_id: int, nmi: str, nem_file):
    """ Load data from NEM file and save to database """

    engine = get_db_engine(meter_id)
    Session = sessionmaker(bind=engine)
    session = Session()

    logging.info("Processing NEM file for Meter %s", meter_id)
    m = read_nem_file(nem_file)
    try:
        channels = m.readings[nmi]
    except KeyError:
        first_nmi = list(m.readings.keys())[0]
        logging.warning("NMI of %s not found, using %s instead", nmi, first_nmi)
        channels = m.readings[first_nmi]

    for ch_name in channels.keys():
        logging.info("Loading data for Meter %s Channel %s", meter_id, ch_name)
        reads = split_into_daily_intervals(channels[ch_name])
        for i, read in enumerate(reads):
            read_start = read[0]
            read_end = read[1]
            read_val = read[2]
            try:
                quality_method = read[4]
            except IndexError:
                quality_method = None
            save_energy_reading(
                session, ch_name, read_start, read_end, read_val, quality_method
            )

            if i == 0:
                first_read = read_start
            last_read = read_end

    session.commit()
    refresh_daily_stats(meter_id, first_read, last_read)
    refresh_monthly_stats(meter_id)
