"""
    metering.loader
    ~~~~~~~~~
    Define the meter data models
"""

from qldtariffs import get_daily_usages
from sqlalchemy.orm import sessionmaker
from . import get_db_engine
from . import get_data_range
from . import get_load_energy_readings
from . import update_daily_total


def refresh_daily_stats(meter_id):
    """ Update the daily totals after loading new readings """

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
                           day_ergon.total, None, None,
                           day_ergon.peak, day_ergon.shoulder,
                           daily_seq[i].peak, daily_seq[i].shoulder)
    session.commit()
