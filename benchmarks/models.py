import hashlib
import re
import urlparse
import xml.etree.ElementTree as ET

from math  import log, exp

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Count
from django.core.exceptions import ValidationError
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.fields import HStoreField


from benchmarks import testminer


class ManifestReduced(models.Model):
    hash = models.CharField(primary_key=True, max_length=40)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.hash


class Manifest(models.Model):
    reduced = models.ForeignKey(ManifestReduced, related_name="manifests", null=True)

    manifest_hash = models.CharField(max_length=40, editable=False, unique=True)
    manifest = models.TextField()

    class Meta:
        ordering = ['-id']

    def __unicode__(self):
        return self.manifest_hash

    def save(self, *args, **kwargs):
        if not self.pk:

            doc = ET.fromstring(self.manifest)
            commit_id_hash = hashlib.sha1()
            for project in settings.BENCHMARK_MANIFEST_PROJECT_LIST:
                project_element_list = doc.findall('.//project[@name="%s"]' % project)
                if project_element_list:
                    for project_element in project_element_list:
                        if project_element.tag == "project":
                            commit_id = project_element.get('revision')
                            commit_id_hash.update(commit_id)

            self.reduced, _ = ManifestReduced.objects.get_or_create(hash=commit_id_hash.hexdigest())
            self.manifest_hash = hashlib.sha1(self.manifest).hexdigest()

        return super(Manifest, self).save(*args, **kwargs)


class Environment(models.Model):
    identifier = models.CharField(max_length=128, unique=True)
    name = models.CharField(max_length=128)

    def save(self, **kwargs):
        if self.name == '' or self.name is None:
            self.name = self.identifier
        return super(Environment, self).save(**kwargs)

    def __unicode__(self):
        if self.name:
            return '%s (%s)' % (self.name, self.identifier)
        else:
            return self.identifier


class Result(models.Model):

    manifest = models.ForeignKey(Manifest, related_name="results", null=True)

    name = models.CharField(max_length=128)
    branch_name = models.CharField(max_length=128, blank=True)

    build_id = models.IntegerField()
    build_url = models.URLField()
    build_number = models.IntegerField()

    gerrit_change_number = models.IntegerField(blank=True, null=True)
    gerrit_patchset_number = models.IntegerField(blank=True, null=True)
    gerrit_change_url = models.URLField(blank=True, null=True)
    gerrit_change_id = models.CharField(max_length=42, blank=True, default="")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    completed = models.BooleanField(default=False)
    reported = models.BooleanField(default=False)

    annotation = models.CharField(max_length=1024, blank=True, null=True)

    class Meta:
        index_together = ["build_id", "name"]
        unique_together = ["build_id", "name"]
        ordering = ['-created_at']

    @property
    def permalink(self):
        return "%s/#/build/%s" % (settings.URL, self.id)

    __baseline__ = False
    __to_compare__ = False

    @property
    def baseline(self):
        # basic per-instance caching
        if self.__baseline__ != False:
            return self.__baseline__

        possible_baselines = self._default_manager.exclude(id=self.id).filter(
            branch_name=self.branch_name,
            gerrit_change_number=None,
            manifest__reduced__hash=self.manifest.reduced.hash
        ).order_by('-created_at')

        # baseline must have environments in common
        environments = [e['environment_id'] for e in self.test_jobs.all().values('environment_id').distinct()]
        self.__baseline__ = None

        for baseline in possible_baselines:
            if baseline.test_jobs.filter(environment_id__in=environments).exists():
                self.__baseline__ = baseline
                break

        return self.__baseline__

    def to_compare(self, results=True):
        # basic per-instance caching
        if self.__to_compare__ != False:
            return self.__to_compare___

        if self.data.count() == 0:
            self.__to_compare__ = None
            return self.__to_compare__

        __to_compare__ = self._default_manager.annotate(
            data_count=Count('data')
        ).filter(
            data_count__gt=0,
            branch_name=self.branch_name,
            gerrit_change_number=None,
            manifest__reduced__hash=self.manifest.reduced.hash
        ).order_by('-created_at')

        if self.gerrit_change_number is None:  # baseline build
            __to_compare__ = __to_compare__.filter(
                created_at__lt=self.created_at
            )

        self.__to_compare__ = __to_compare__.first()
        return self.__to_compare__


    @property
    def testjobs_updated(self):
        if not self.updated_at:
            return True
        jobs = self.test_jobs.filter(updated_at__gt=self.updated_at)
        return jobs.exists()

    def __unicode__(self):
        return "%s - %s" % (self.pk, self.build_url)


class TestJob(models.Model):
    result = models.ForeignKey('Result', related_name="test_jobs")
    environment = models.ForeignKey('Environment', related_name="test_jobs", null=True)

    id = models.CharField(primary_key=True, max_length=100, blank=False)

    name = models.CharField(blank=True, default="", max_length=512)
    url = models.URLField(blank=True, null=True)
    status = models.CharField(blank=True, default="", max_length=16)
    definition = models.TextField(blank=True, null=True)
    initialized = models.BooleanField(default=False)
    completed = models.BooleanField(default=False)
    resubmitted = models.BooleanField(default=False)
    data = models.FileField(null=True, blank=True)
    testrunnerclass = models.CharField(blank=True, default="GenericLavaTestSystem", max_length=128)
    testrunnerurl = models.CharField(blank=True, default="https://validation.linaro.org/", max_length=256)

    results_loaded = models.BooleanField(default=False)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    metadata = HStoreField(default=dict, blank=True)

    def save(self, *args, **kwargs):
        jenkins_id_re = re.compile(r"J\d+_[\w\d\_\.]+")
        if jenkins_id_re.match(self.id):
            self.testrunnerclass = "ArtJenkinsTestResults"
            self.url = self.result.build_url
        super(TestJob, self).save(*args, **kwargs)

        test_jobs = self.result.test_jobs
        self.result.completed = (test_jobs.count() == test_jobs.filter(completed=True).count())
        self.result.save()

    class Meta:
        ordering = ['-created_at']

    def __unicode__(self):
        return '<%s %s#%s %s>' % (self.id, self.result.build_id, self.result.name, self.status)

    def can_resubmit(self):
        # check if job already was resubmitted
        if self.resubmitted:
            return False
        # check status
        if self.status in ['Complete', 'Running', 'Submitted', '']:
            return False
        # check if this is single node
        if '.' not in self.id:
            return True
        # check if this is 'target' of multinode
        # assume that multinode jobs have the same ID before 'dot'
        if self.id.split('.')[1] != "0" :
            return False
        return True

    def get_tester(self):
        host = urlparse.urlsplit(self.testrunnerurl).netloc
        (username, password) = settings.CREDENTIALS[host]

        tester_class = getattr(testminer, self.testrunnerclass)
        return tester_class(self.testrunnerurl, username, password)

    @property
    def data_filetype(self):
        if self.data.name is None:
            return None
        return self.data.name.split('.')[-1]

    @property
    def result_data(self):
        return self.result.data.filter(test_job_id=self.id).prefetch_related('benchmark').order_by('benchmark__name', "name")


class BenchmarkGroup(models.Model):

    name = models.CharField(max_length=128, unique=True)

    def save(self, *args, **kwargs):
        # calling validation here since this object is usually created in the
        # background, so there are no ModelForms involved.
        self.full_clean()
        super(BenchmarkGroup, self).save(*args, **kwargs)

    def __unicode__(self):
        return self.name


def geomean(values):
    # The intuitive/naive way of calculating a geometric mean (first
    # multiply the n values, then take the nth-root of the result) does not
    # work in practice. When you multiple an large enough amount of large
    # enough numbers, their product will oferflow the float representation,
    # and the result will be Infinity.
    #
    # Will use the alternative method described in
    # https://en.wikipedia.org/wiki/Geometric_mean -- topic "Relationship
    # with arithmetic mean of logarithms" -- which is exp(sum(log(x_i)/n))
    #
    # zeros are discarded
    values = [v for v in values if v > 0]
    if len(values) == 0:
        return 0

    n = len(values)
    log_sum = reduce(lambda x,y: x + y, map(log, values))
    return exp(log_sum/n)


class BenchmarkGroupSummary(models.Model):
    group = models.ForeignKey(BenchmarkGroup, related_name='progress_data')
    environment = models.ForeignKey(Environment, related_name='progress_data', null=True)
    result = models.ForeignKey(Result, related_name='progress_data')
    test_job_id = models.CharField(max_length=100, blank=False, null=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, null=False)
    measurement = models.FloatField(null=False)
    values = ArrayField(models.FloatField(), default=list)

    def save(self, *args, **kwargs):
        if self.values:
            self.measurement = geomean(self.values)
        super(BenchmarkGroupSummary, self).save(*args, **kwargs)

    @property
    def name(self):
        return "Geometric mean"


class Benchmark(models.Model):
    name = models.CharField(max_length=64)
    group = models.ForeignKey(BenchmarkGroup, related_name='benchmarks', null=True)

    @property
    def full_name(self):
        return self.group.name + self.name

    def __unicode__(self):
        return self.name


class ResultData(models.Model):
    result = models.ForeignKey(Result, related_name="data")
    benchmark = models.ForeignKey(Benchmark, related_name="data")

    # can't be a proper ForeignKey because it breaks django_dynamic_fixtures
    # (maybe because the primary key is not autogenerated?)
    test_job_id = models.CharField(max_length=100, blank=False, null=True, db_index=True)

    name = models.CharField(max_length=256)
    board = models.CharField(default="default", max_length=128)
    measurement = models.FloatField(default=0)
    stdev = models.FloatField(default=0)

    values = ArrayField(models.FloatField(), default=list)

    created_at = models.DateTimeField(default=timezone.now)

    def _mean(self, data):
        n = len(data)
        if n < 1:
            return 0
        return sum(data)/float(n)

    def _ss(self, data):
        c = self._mean(data)
        ss = sum((x-c)**2 for x in data)
        return ss

    def _stddev(self, data):
        n = len(data)
        if n < 2:
            return 0
        ss = self._ss(data)
        pvar = ss/n
        return pvar**0.5

    def save(self, *args, **kwargs):
        if self.measurement and not self.values:
            self.values = [self.measurement]

        if self.values:
            self.measurement = self._mean(self.values)
            self.stdev = self._stddev(self.values)

        return super(ResultData, self).save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']

    def __unicode__(self):
        return "%s - %s: %s" % (self.benchmark, self.name, self.measurement)
