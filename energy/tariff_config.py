""" Specifies the costs of each tariff type
"""

import datetime


METER_SERVICES_CHARGE_PRIMARY = 9.838  # cents/day
METER_SERVICES_CHARGE_CONTROLLED = 2.951  # cents/day
METER_SERVICES_CHARGE_EXPORT = 6.887  # cents/day

RESIDENTIAL_GS_USAGE = 27.071  # cents/kWh
RESIDENTIAL_GS_SUPPLY_CHARGE = 98.5292  # cents/day

RESIDENTIAL_TOU_USAGE_PEAK = 61.4515  # cents/kWh
RESIDENTIAL_TOU_USAGE_OFFPEAK = 21.8449  # cents/kWh
RESIDENTIAL_TOU_SUPPLY_CHARGE = 111.4366  # cents/day

RESIDENTIAL_TOUD_USAGE = 16.4835  # cents/kWh
RESIDENTIAL_TOUD_SUPPLY_CHARGE = 66.5654  # cents/day
RESIDENTIAL_TOUD_DEMAND_PEAK = 67.969  # $/kw/mth
RESIDENTIAL_TOUD_DEMAND_OFFPEAK = 12.3838  # $/kw/mth

PEAK_MONTHS = [12, 1, 2]  # Months for which peak charges apply
PEAK_WINDOW_START = datetime.time(15, 0, 0)
PEAK_WINDOW_END = datetime.time(21, 30, 0)