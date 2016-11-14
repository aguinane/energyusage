import arrow
import datetime
from datetime import timedelta, date
import calendar
import statistics
from . import tariff_config as tc
from .usage import UsageStats, get_power_data, in_peak_season


class DailyUsage(object):
    """ Used to calculate daily energy costs for a period
    """
    def __init__(self, meter_id, start_date, end_date):
        self.meter_id = meter_id
        self.start_date = arrow.get(start_date).date()
        self.end_date = arrow.get(start_date).date()
        daily_usage = dict()
        for single_date in self.daterange(start_date, end_date):
            sd = arrow.get(single_date)
            ed = sd.replace(days=+1)
            usage = get_power_data(self.meter_id, sd.datetime, ed.datetime)
            daily_usage[single_date.strftime("%Y-%m-%d")] = UsageStats(usage)
        self.daily_usage = daily_usage

    def daterange(self, start_date, end_date):
        """ List all days between two date objects
        """
        for n in range(int ((end_date - start_date).days)):
            yield start_date + timedelta(n)


class GeneralSupplyTariff(object):
    """ Used to calculate the costs of a general supply tariff
    """

    def __init__(self, meter_id):
        self.meter_id = meter_id
        self.daily_meter_services_charge = tc.METER_SERVICES_CHARGE_PRIMARY
        self.daily_supply_charge = tc.RESIDENTIAL_GS_SUPPLY_CHARGE
        self.consumption_rate = tc.RESIDENTIAL_GS_USAGE

    def calculate_bill(self, start_date, end_date):
        """ Calculate charges for specified period
        """
        num_days = (end_date - start_date).days
        self.meter_services_charge = self.daily_meter_services_charge * num_days
        self.supply_charge = self.daily_supply_charge * num_days

        self.consumption_kWh = 0
        du = DailyUsage(self.meter_id, start_date, end_date)
        for day in du.daily_usage.keys():
            self.consumption_kWh += du.daily_usage[day].consumption_total / 1000
        self.consumption_charge = self.consumption_rate * self.consumption_kWh
        self.total_cost = self.meter_services_charge + \
            self.supply_charge + self.consumption_charge
        return self.total_cost


class TimeofUseTariff(object):
    """ Used to calculate the costs of a time of use tariff
    """

    def __init__(self, meter_id):
        self.meter_id = meter_id
        self.daily_meter_services_charge = tc.METER_SERVICES_CHARGE_PRIMARY
        self.daily_supply_charge = tc.RESIDENTIAL_TOU_SUPPLY_CHARGE
        self.consumption_rate_peak = tc.RESIDENTIAL_TOU_USAGE_PEAK
        self.consumption_rate_offpeak = tc.RESIDENTIAL_TOU_USAGE_OFFPEAK

    def calculate_bill(self, start_date, end_date):
        """ Calculate charges for specified period
        """
        num_days = (end_date - start_date).days
        self.meter_services_charge = self.daily_meter_services_charge * num_days
        self.supply_charge = self.daily_supply_charge * num_days

        self.peak_consumption_kWh = 0
        self.offpeak_consumption_kWh = 0

        du = DailyUsage(self.meter_id, start_date, end_date)
        for day in du.daily_usage.keys():
            self.peak_consumption_kWh += du.daily_usage[day].consumption_peak / 1000
            self.offpeak_consumption_kWh += du.daily_usage[day].consumption_offpeak / 1000

        self.peak_consumption_charge = self.consumption_rate_peak * self.peak_consumption_kWh
        self.offpeak_consumption_charge = self.consumption_rate_offpeak * \
            self.offpeak_consumption_kWh

        self.total_cost = self.meter_services_charge + self.supply_charge + \
            self.peak_consumption_charge + self.offpeak_consumption_charge
        return self.total_cost


class DemandTariff(object):
    """ Used to calculate the costs of a time of use demand tariff
    """

    def __init__(self, meter_id):
        self.meter_id = meter_id
        self.daily_meter_services_charge = tc.METER_SERVICES_CHARGE_PRIMARY
        self.daily_supply_charge = tc.RESIDENTIAL_TOUD_SUPPLY_CHARGE
        self.consumption_rate = tc.RESIDENTIAL_TOUD_USAGE
        self.demand_charge_peak = tc.RESIDENTIAL_TOUD_DEMAND_PEAK
        self.demand_charge_offpeak = tc.RESIDENTIAL_TOUD_DEMAND_OFFPEAK

    def calculate_bill(self, start_date, end_date):
        """ Calculate charges for specified period
        """
        num_days = (end_date - start_date).days
        self.meter_services_charge = self.daily_meter_services_charge * num_days
        self.supply_charge = self.daily_supply_charge * num_days
        self.consumption_kWh = 0

        du = DailyUsage(self.meter_id, start_date, end_date)
        for day in du.daily_usage.keys():
            self.consumption_kWh += du.daily_usage[day].consumption_total / 1000

        self.consumption_charge = self.consumption_rate * self.consumption_kWh

        # Calculate daily peak
        peak_days = dict()
        for day in du.daily_usage.keys():
            daily_peak = du.daily_usage[day].demand_abs_peak
            avg_peak = du.daily_usage[day].demand_avg_peak
            peak_days[day] = (daily_peak, avg_peak)
        self.peak_days = peak_days

        # Sort and get top 4 demand days
        top_four_days = []
        for i, day in enumerate(sorted(peak_days, key=peak_days.get, reverse=True)):
            if i < 4:
                top_four_days.append(day)
        self.top_four_days = top_four_days

        # Calculate average demand
        peak_demands = []
        for day in top_four_days:
            peak_demands.append(du.daily_usage[day].demand_avg_peak)

        if peak_demands:
            self.peak_demand_kW = statistics.mean(peak_demands) / 1000
        else:
            self.peak_demand_kW = 0

        # Determine rate depending on if peak season
        try:
            peak_day = top_four_days[0]
        except IndexError:
            peak_day = arrow.get(start_date).format('YYYY-MM-DD')
        self.peak_season = in_peak_season(peak_day)
        if self.peak_season:
            self.demand_charge = self.peak_demand_kW * self.demand_charge_peak
        else:
            # The  off  peak  demand  quantity  is  subject  to  a  minimum
            # chargeable  demand  of  3kW
            if self.peak_demand_kW < 3:
                self.peak_demand_kW = 3
            self.demand_charge = self.peak_demand_kW * \
                self.demand_charge_offpeak * 100  # in cents

        # Daily calculation should scale demand charge
        days_in_month = calendar.monthrange(
            start_date.year, start_date.month)[1]
        self.demand_charge = self.demand_charge * (num_days / days_in_month)
        self.total_cost = self.meter_services_charge + \
            self.supply_charge + self.consumption_charge + self.demand_charge
        return self.total_cost



def get_total_consumption(meter_id, start_date, end_date):
    for r in get_energy_data(meter_id, start_date, end_date):
        dTime = arrow.get(r.reading_date)
        ts = int(dTime.timestamp * 1000)
        impWh = r.imp
        chartdata['consumption'].append([ts, impWh])
