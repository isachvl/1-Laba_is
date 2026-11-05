import unittest
from client import metrics


class MetricsTest(unittest.TestCase):
    def test_assignment(self):
        m = metrics(0, .4, 2.4, 101)
        self.assertAlmostEqual(m['ttft_s'], .4)
        self.assertAlmostEqual(m['tpot_s'], .02)
        self.assertAlmostEqual(m['e2e_s'], 2.4)

    def test_single_token(self):
        self.assertIsNone(metrics(0, .4, .4, 1)['tpot_s'])


if __name__ == '__main__':
    unittest.main()
