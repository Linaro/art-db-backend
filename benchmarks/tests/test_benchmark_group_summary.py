from django.test import TestCase

from benchmarks.models import Result, BenchmarkGroup
from benchmarks.models import BenchmarkGroupSummary
from django_dynamic_fixture import G

from benchmarks.testing import MANIFEST

class BenchmarkGroupSummaryTest(TestCase):

    def test_geomean(self):
        result = G(Result, manifest=MANIFEST())
        progress = G(BenchmarkGroupSummary, values=[1,2], result=result)
        self.assertAlmostEqual(1.4142, progress.measurement, delta=0.0001)

    def test_geomean_with_zeros(self):
        result = G(Result, manifest=MANIFEST())
        progress = G(BenchmarkGroupSummary, values=[1,2,0], result=result)
        self.assertAlmostEqual(1.4142, progress.measurement, delta=0.0001)

    def test_geomean_with_only_zeros(self):
        result = G(Result, manifest=MANIFEST())
        progress = G(BenchmarkGroupSummary, values=[0,0,0], result=result)
        self.assertAlmostEqual(0, progress.measurement, delta=0.0001)
