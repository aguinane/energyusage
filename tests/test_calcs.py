import unittest
from energy.usage import UsageStats
from energy.usage import in_peak_period
from energy.usage import convert_w_to_wh, convert_wh_to_w


class TestEnergy(unittest.TestCase):
    """ Tests some functions outside the web app
    """

    def test_peak_times(self):
        """ Check that peak periods are being determined correctly
        """
        # Test seasons
        self.assertFalse(in_peak_period('2015-11-30 19:00:00'))
        self.assertTrue(in_peak_period('2016-12-01 19:00:00'))
        self.assertTrue(in_peak_period('2016-01-01 19:00:00'))
        self.assertFalse(in_peak_period('2016-04-01 19:00:00'))

        # Test time edge cases
        self.assertFalse(in_peak_period('2016-01-01 15:00:00'))
        self.assertTrue(in_peak_period('2016-01-01 15:01:00'))
        self.assertTrue(in_peak_period('2016-01-01 21:30:00'))
        self.assertFalse(in_peak_period('2016-01-01 21:31:00'))

    def test_energy_to_power_conversion(self):
        """ Test wh to w conversions
        """
        self.assertEqual(convert_wh_to_w(Wh=5, hours=1), 5)
        self.assertEqual(convert_wh_to_w(Wh=2.5, hours=0.5), 5)

        self.assertEqual(convert_w_to_wh(W=5, hours=1), 5)
        self.assertEqual(convert_w_to_wh(W=5, hours=0.5), 2.5)


class TestUsage(unittest.TestCase):
    """ Test usage aggregation
    """

    def test_usage_calcs(self):
        """ Test usage aggregation
        """
        usage = [('2016-01-01 14:00:00', 0.005),
                 ('2016-01-01 14:30:00', 0.005),
                 ('2016-01-01 15:00:00', 0.005),
                 ('2016-01-01 15:30:00', 0.015),
                 ('2016-01-01 16:00:00', 0.025),
                 ('2016-01-01 16:30:00', 0.030),
                 ]

        u = UsageStats(usage)
        self.assertEqual(u.consumption_offpeak, 0.015)
        self.assertEqual(u.consumption_peak, 0.070)
        self.assertEqual(u.consumption_total, 0.085)
        self.assertAlmostEqual(u.demand_avg_peak, 0.011, places=3)


if __name__ == '__main__':
    unittest.main()
