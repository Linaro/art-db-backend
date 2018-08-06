import hashlib
import json
from StringIO import StringIO
from mock import patch

from django_dynamic_fixture import G
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from django.utils import timezone
from dateutil.relativedelta import relativedelta

from benchmarks import models
from benchmarks.tests import get_file


from benchmarks.testing import MANIFEST, MINIMAL_XML


class TestJobTests(APITestCase):

    def setUp(self):
        user = User.objects.create_superuser('test', 'email@test.com', 'test')
        self.client.force_authenticate(user=user)

    @patch('benchmarks.testminer.GenericLavaTestSystem.call_xmlrpc', lambda *x, **y: "111")
    @patch('benchmarks.tasks.update_jenkins.delay', lambda *x, **y: None)
    @patch('benchmarks.tasks.set_testjob_results.apply', lambda *x, **y: None)
    @patch.dict('django.conf.settings.CREDENTIALS', {'validation.linaro.org': ("hej", "ho")})
    def test_resubmit_incomplete(self):
        testjob = G(models.TestJob, id="000", status="Incomplete", result__manifest=MANIFEST())

        response = self.client.get('/api/testjob/%s/resubmit/' % testjob.id)

        self.assertEqual(response.data[0]['id'], "111")

        self.assertEqual(models.TestJob.objects.count(), 2)
        self.assertEqual(models.TestJob.objects.filter(id="000").exists(), True)
        self.assertEqual(models.TestJob.objects.filter(id="111").exists(), True)

    @patch('benchmarks.testminer.GenericLavaTestSystem.call_xmlrpc', lambda *x, **y: "111")
    @patch('benchmarks.tasks.update_jenkins.delay', lambda *x, **y: None)
    @patch('benchmarks.tasks.set_testjob_results.apply', lambda *x, **y: None)
    @patch.dict('django.conf.settings.CREDENTIALS', {'validation.linaro.org': ("hej", "ho")})
    def test_resubmit_canceled(self):
        testjob = G(models.TestJob, id="000", status="Canceled", result__manifest=MANIFEST())

        response = self.client.get('/api/testjob/%s/resubmit/' % testjob.id)

        self.assertEqual(response.data[0]['id'], "111")

        self.assertEqual(models.TestJob.objects.count(), 2)
        self.assertEqual(models.TestJob.objects.filter(id="000").exists(), True)
        self.assertEqual(models.TestJob.objects.filter(id="111").exists(), True)

    @patch('benchmarks.testminer.GenericLavaTestSystem.call_xmlrpc', lambda *x, **y: "111")
    @patch('benchmarks.tasks.update_jenkins.delay', lambda *x, **y: None)
    @patch('benchmarks.tasks.set_testjob_results.apply', lambda *x, **y: None)
    @patch.dict('django.conf.settings.CREDENTIALS', {'validation.linaro.org': ("hej", "ho")})
    def test_resubmit_resultsmissing(self):
        testjob = G(models.TestJob, id="000", status="Results Missing", result__manifest=MANIFEST())

        response = self.client.get('/api/testjob/%s/resubmit/' % testjob.id)

        self.assertEqual(response.data[0]['id'], "111")

        self.assertEqual(models.TestJob.objects.count(), 2)
        self.assertEqual(models.TestJob.objects.filter(id="000").exists(), True)
        self.assertEqual(models.TestJob.objects.filter(id="111").exists(), True)

    @patch('benchmarks.testminer.GenericLavaTestSystem.call_xmlrpc', lambda *x, **y: "111")
    @patch('benchmarks.tasks.update_jenkins.delay', lambda *x, **y: None)
    @patch('benchmarks.tasks.set_testjob_results.apply', lambda *x, **y: None)
    @patch.dict('django.conf.settings.CREDENTIALS', {'validation.linaro.org': ("hej", "ho")})
    def test_resubmit_with_status_completed(self):

        testjob = G(models.TestJob, status='Complete', result__manifest=MANIFEST())

        response = self.client.get('/api/testjob/%s/resubmit/' % testjob.id)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(models.TestJob.objects.count(), 1)
        self.assertEqual(models.TestJob.objects.filter(id="111").exists(), False)

    @patch('benchmarks.testminer.GenericLavaTestSystem.call_xmlrpc', lambda *x, **y: "111")
    @patch('benchmarks.tasks.update_jenkins.delay', lambda *x, **y: None)
    @patch('benchmarks.tasks.set_testjob_results.apply', lambda *x, **y: None)
    @patch.dict('django.conf.settings.CREDENTIALS', {'validation.linaro.org': ("hej", "ho")})
    def test_resubmit_with_status_running(self):

        testjob = G(models.TestJob, status='Running', result__manifest=MANIFEST())

        response = self.client.get('/api/testjob/%s/resubmit/' % testjob.id)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(models.TestJob.objects.count(), 1)
        self.assertEqual(models.TestJob.objects.filter(id="111").exists(), False)

    @patch('benchmarks.testminer.GenericLavaTestSystem.call_xmlrpc', lambda *x, **y: "111")
    @patch('benchmarks.tasks.update_jenkins.delay', lambda *x, **y: None)
    @patch('benchmarks.tasks.set_testjob_results.apply', lambda *x, **y: None)
    @patch.dict('django.conf.settings.CREDENTIALS', {'validation.linaro.org': ("hej", "ho")})
    def test_resubmit_with_status_submitted(self):

        testjob = G(models.TestJob, status='Submitted', result__manifest=MANIFEST())

        response = self.client.get('/api/testjob/%s/resubmit/' % testjob.id)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(models.TestJob.objects.count(), 1)
        self.assertEqual(models.TestJob.objects.filter(id="111").exists(), False)


class ResultTests(APITestCase):

    def setUp(self):
        user = User.objects.create_superuser('test', 'email@test.com', 'test')
        self.client.force_authenticate(user=user)

    def test_get_1(self):
        response = self.client.get('/api/result/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)

    def test_get_2(self):
        manifest = G(models.Manifest, manifest=MINIMAL_XML)
        G(models.Result, id=123, manifest=manifest)

        response = self.client.get('/api/result/123/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], 123)

    @patch('benchmarks.tasks.update_jenkins.apply_async', lambda **kwargs: None)
    @patch('benchmarks.tasks.set_testjob_results.apply_async', lambda **kwargs: None)
    def test_post_1(self):

        data = {
            'build_url': 'http://linaro.org',
            'build_number': 200,
            'build_id': 20,
            'name': u'linaro-art-stable-m-build-juno',
            'url': u'http://dynamicfixture1.com',
            'id': u'123',
            'manifest': MINIMAL_XML
        }

        response = self.client.post('/api/result/', data=data)

        self.assertEqual(models.Manifest.objects.count(), 1)
        self.assertEqual(response.status_code, 201)

    @patch('benchmarks.tasks.update_jenkins.apply_async', lambda **kwargs: None)
    @patch('benchmarks.tasks.set_testjob_results.apply_async', lambda **kwargs: None)
    def test_post_2(self):

        data = {
            'build_url': 'http://linaro.org',
            'name': u'linaro-art-stable-m-build-juno',
            'url': u'http://dynamicfixture1.com',
            'id': u'123',
            'build_number': 200,
            'build_id': 20,
            'test_jobs': '655839.0, 655838.0, 655838.0',
            'manifest': MINIMAL_XML
        }

        response = self.client.post('/api/result/', data=data)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(models.Manifest.objects.count(), 1)
        self.assertEqual(models.TestJob.objects.count(), 2)

        items = models.TestJob.objects.values_list('id', flat=True)
        self.assertIn('655839.0', items)
        self.assertIn('655838.0', items)

    @patch('benchmarks.tasks.update_jenkins.apply_async', lambda **kwargs: None)
    @patch('benchmarks.tasks.set_testjob_results.apply_async', lambda *kwargs: None)
    def test_post_3(self):

        data_1 = {
            'build_url': 'http://linaro.org',
            'name': u'linaro-art-stable-m-build-juno',
            'url': u'http://dynamicfixture1.com',
            'manifest': MINIMAL_XML,
            'build_number': 200,
            'build_id': 200
        }

        data_2 = {
            'build_url': 'http://linaro.org',
            'name': u'linaro-art-stable-m-build-juno',
            'url': u'http://dynamicfixture1.com',
            'manifest': MINIMAL_XML,
            'build_number': 201,
            'build_id': 201
        }

        response_1 = self.client.post('/api/result/', data=data_1)
        response_2 = self.client.post('/api/result/', data=data_2)

        self.assertEqual(response_1.status_code, 201)
        self.assertEqual(response_2.status_code, 201)

        self.assertEqual(models.Result.objects.count(), 2)
        self.assertEqual(models.Manifest.objects.count(), 1)

    @patch('benchmarks.tasks.update_jenkins.apply_async', lambda **kwargs: None)
    @patch('benchmarks.tasks.set_testjob_results.apply_async', lambda **kwargs: None)
    def test_post_4(self):
        build_id = 200
        build_number = 20

        data_1 = {
            'build_url': 'http://linaro.org',
            'name': u'linaro-art-stable-m-build-juno',
            'url': u'http://dynamicfixture1.com',
            'manifest': MINIMAL_XML,
            'build_number': build_number,
            'build_id': build_id
        }

        data_2 = {
            'build_url': 'http://linaro.org',
            'name': u'linaro-art-stable-m-build-juno',
            'url': u'http://linaro.org',
            'manifest': MINIMAL_XML,
            'build_number': build_number,
            'build_id': build_id
        }

        response_1 = self.client.post('/api/result/', data=data_1)
        response_2 = self.client.post('/api/result/', data=data_2)

        self.assertEqual(response_1.status_code, 201)
        self.assertEqual(response_2.status_code, 201)

        self.assertEqual(models.Result.objects.count(), 1)
        self.assertEqual(models.Manifest.objects.count(), 1)

    @patch('benchmarks.tasks.update_jenkins.apply_async', lambda **kwargs: None)
    @patch('benchmarks.tasks.set_testjob_results.apply_async', lambda **kwargs: None)
    def test_post_5(self):

        data = {
            'build_url': 'http://linaro.org',
            'name': u'linaro-art-stable-m-build-juno',
            'url': u'http://dynamicfixture1.com',
            'build_number': 200,
            'build_id': 20,
            'manifest': MINIMAL_XML,
            'created_at': '2016-01-06 09:00:01',
            'test_jobs': " 111, 222 "
        }

        response = self.client.post('/api/result/', data=data)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(models.Manifest.objects.count(), 1)
        self.assertEqual(models.TestJob.objects.count(), 2)
        self.assertEqual(response.data['created_at'], '2016-01-06T09:00:01Z')

    @patch('benchmarks.tasks.update_jenkins.apply_async', lambda **kwargs: None)
    @patch('benchmarks.tasks.set_testjob_results.apply_async', lambda **kwargs: None)
    def test_post_with_results(self):

        data = {
            'build_url': 'http://linaro.org',
            'name': u'linaro-art-stable-m-build-juno',
            'url': u'http://dynamicfixture1.com',
            'build_number': 200,
            'build_id': 20,
            'manifest': MINIMAL_XML,
            'test_jobs': " 111, 222 ",
            'results': [
                {"benchmark": "benchmark", "name": "load", "measurement": 3},
                {"benchmark": "benchmark", "name": "boot", "measurement": 10}
            ]
        }

        response = self.client.post('/api/result/', data=data, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(models.Manifest.objects.count(), 1)
        self.assertEqual(models.ResultData.objects.count(), 2)

        self.assertEqual(models.ResultData.objects.get(name="load").measurement, 3)
        self.assertEqual(models.ResultData.objects.get(name="boot").measurement, 10)

    @patch('benchmarks.tasks.update_jenkins.apply_async', lambda **kwargs: None)
    @patch('benchmarks.tasks.set_testjob_results.apply_async', lambda **kwargs: None)
    def test_post_with_results_empty(self):

        data = {
            'build_url': 'http://linaro.org',
            'name': u'linaro-art-stable-m-build-juno',
            'url': u'http://dynamicfixture1.com',
            'build_number': 200,
            'build_id': 20,
            'manifest': MINIMAL_XML,
            'test_jobs': " 111, 222 ",
            'results': []
        }

        response = self.client.post('/api/result/', data=data)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(models.Manifest.objects.count(), 1)
        self.assertEqual(models.ResultData.objects.count(), 0)

    @patch('benchmarks.tasks.update_jenkins.apply_async', lambda **kwargs: None)
    @patch('benchmarks.tasks.set_testjob_results.apply_async', lambda **kwargs: None)
    def test_add_test_jobs_to_existing_result_object(self):

        initial_data = {
            'build_url': 'http://linaro.org',
            'name': u'linaro-art-stable-m-build-juno',
            'url': u'http://dynamicfixture1.com',
            'build_number': 200,
            'build_id': 20,
            'manifest': MINIMAL_XML,
            'created_at': '2016-01-06 09:00:01',
            'test_jobs': " 111, 222 "
        }

        response0 = self.client.post('/api/result/', data=initial_data)
        self.assertEqual(response0.data['created_at'], '2016-01-06T09:00:01Z')

        additional_data = {
            'build_id': 20,
            'name': u'linaro-art-stable-m-build-juno',
            'test_jobs': " 333 "
        }
        response = self.client.post('/api/result/', data=additional_data)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(models.Result.objects.count(), 1)
        self.assertEqual(models.Manifest.objects.count(), 1)
        self.assertEqual(models.TestJob.objects.count(), 3)

    @patch('benchmarks.tasks.update_jenkins.apply_async', lambda **kwargs: None)
    @patch('benchmarks.tasks.set_testjob_results.apply_async', lambda **kwargs: None)
    def test_add_existing_test_jobs_to_existing_result_object(self):

        initial_data = {
            'build_url': 'http://linaro.org',
            'name': u'linaro-art-stable-m-build-juno',
            'url': u'http://dynamicfixture1.com',
            'build_number': 200,
            'build_id': 20,
            'manifest': MINIMAL_XML,
            'created_at': '2016-01-06 09:00:01',
            'test_jobs': " 111, 222 "
        }

        response0 = self.client.post('/api/result/', data=initial_data)
        self.assertEqual(response0.data['created_at'], '2016-01-06T09:00:01Z')

        additional_data = {
            'build_id': 20,
            'name': u'linaro-art-stable-m-build-juno',
            'test_jobs': " 111, 222 "
        }
        response = self.client.post('/api/result/', data=additional_data)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(models.Result.objects.count(), 1)
        self.assertEqual(models.Manifest.objects.count(), 1)
        self.assertEqual(models.TestJob.objects.count(), 2)

    @patch.dict('django.conf.settings.CREDENTIALS', {'jenkins.linaro.org': ("hej", "ho")})
    def test_post_already_with_testjob_results(self):
        data = {
            'build_url': 'http://jenkins.linaro.org/foo/bar/baz/1',
            'name': u'linaro-art-stable-m-build-juno',
            'url': u'http://dynamicfixture1.com',
            'build_number': 200,
            'build_id': 200,
            'manifest': MINIMAL_XML,
            'created_at': '2016-01-06 09:00:01',
            # NOTE NO 'test_jobs'
            'environment1.json': StringIO(json.dumps({
                "benchmarks": {
                    "benchmarks/group1/foo.foo1": [1,2,2],
                    "benchmarks/group2/bar.bar1": [3,3,4],
                }
            })),

            "environment2.json": StringIO(json.dumps({
                "benchmarks": {
                    "benchmarks/group1/foo.foo1": [2,2,3],
                    "benchmarks/group2/bar.bar1": [4,4,5],
                }
            })),
        }
        response = self.client.post('/api/result/', data=data)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(models.Result.objects.count(), 1)
        self.assertEqual(models.Manifest.objects.count(), 1)
        self.assertEqual(models.TestJob.objects.count(), 2)

        self.assertEqual(models.Environment.objects.count(), 2)
        self.assertEqual(models.BenchmarkGroup.objects.count(), 3) # 2 + root


    def test_baseline_1(self):

        env = G(models.Environment)

        baseline = G(models.Result,
                     manifest=MANIFEST(),
                     branch_name="master",
                     gerrit_change_number=None)

        current = G(models.Result,
                    manifest=MANIFEST(),
                    branch_name="master",
                    gerrit_change_number=123)

        G(models.ResultData,
          result=current,
          benchmark__name="load",
          name="load-avg",
          measurement=10)

        G(models.TestJob,
          result=current,
          environment=env)

        G(models.ResultData,
          result=baseline,
          benchmark__name="load",
          name="load-avg",
          measurement=10)

        G(models.TestJob,
          result=baseline,
          environment=env)

        response = self.client.get('/api/result/%s/baseline/' % current.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], baseline.id)

    def test_baseline_2(self):

        result_1 = G(models.Result,
                     manifest=MANIFEST(),
                     branch_name="master",
                     gerrit_change_number=123)

        G(models.ResultData,
          result=result_1,
          benchmark__name="load",
          name="load-avg",
          measurement=10)

        response = self.client.get('/api/result/%s/baseline/' % result_1.pk)

        self.assertEqual(response.status_code, 204)

    def test_baseline_3(self):
        now = timezone.now()
        yesterday = now - relativedelta(days=1)

        env = G(models.Environment)
        env2 = G(models.Environment)

        wrong_baseline = G(models.Result,
                           manifest=MANIFEST(),
                           branch_name="master",
                           created_at=now,
                           gerrit_change_number=None)

        baseline = G(models.Result,
                     manifest=MANIFEST(),
                     branch_name="master",
                     created_at=yesterday,
                     gerrit_change_number=None)

        current = G(models.Result,
                    manifest=MANIFEST(),
                    branch_name="master",
                    gerrit_change_number=123)

        G(models.ResultData,
          result=current,
          benchmark__name="load",
          name="load-avg",
          measurement=10)

        G(models.TestJob,
          result=current,
          environment=env)

        G(models.ResultData,
          result=wrong_baseline,
          benchmark__name="load",
          name="load-avg",
          measurement=10)

        G(models.TestJob,
          result=wrong_baseline,
          environment=env2)

        G(models.ResultData,
          result=baseline,
          benchmark__name="load",
          name="load-avg",
          measurement=10)

        G(models.TestJob,
          result=baseline,
          environment=env)

        response = self.client.get('/api/result/%s/baseline/' % current.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], baseline.id)


class ManifestTests(APITestCase):

    def setUp(self):
        user = User.objects.create_superuser('test', 'email@test.com', 'test')
        self.client.force_authenticate(user=user)

    def test_get_1(self):
        response = self.client.get('/api/manifest/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)

    def test_get_2(self):
        manifest_hash = hashlib.sha1(MINIMAL_XML).hexdigest()

        models.Manifest.objects.create(manifest=MINIMAL_XML)

        response = self.client.get('/api/manifest/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['manifest_hash'], manifest_hash)

    def test_search(self):
        xml_1 = MINIMAL_XML + " "
        xml_2 = MINIMAL_XML + "  "

        manifest_hash_1 = hashlib.sha1(xml_1).hexdigest()
        manifest_hash_2 = hashlib.sha1(xml_1).hexdigest()

        models.Manifest.objects.create(manifest=xml_1)
        models.Manifest.objects.create(manifest=xml_2)

        response = self.client.get('/api/manifest/?manifest_hash=test')
        self.assertEqual(response.data['count'], 0)

        response = self.client.get('/api/manifest/?manifest_hash=%s' % manifest_hash_1)
        self.assertEqual(response.data['count'], 1)

        response = self.client.get('/api/manifest/?manifest_hash=%s' % manifest_hash_2)
        self.assertEqual(response.data['count'], 1)


class StatsTest(APITestCase):

    def setUp(self):
        user = User.objects.create_superuser('test', 'email@test.com', 'test')
        self.client.force_authenticate(user=user)

    @patch('django.conf.settings.IGNORE_GERRIT', False)
    def test_missing_parameters(self):
        now = timezone.now()
        yesterday = now - relativedelta(days=1)

        baseline = G(models.Result,
              manifest=MANIFEST(),
              branch_name='master',
              name="TheProject",
              created_at=yesterday,
              gerrit_change_number=None)

        patched = G(models.Result,
             manifest=MANIFEST(),
             branch_name='master',
             name="TheProject",
             created_at=now,
             gerrit_change_number=123)

        group = G(models.BenchmarkGroup, name='foo/')
        benchmark = G(models.Benchmark, group=group, name="TheBenchmark")

        G(models.ResultData,
          result=baseline,
          benchmark=benchmark,
          name="TheBenchmark",
          measurement=5)

        G(models.ResultData,
          result=patched,
          benchmark=benchmark,
          name="TheBenchmark",
          measurement=10)

        response = self.client.get('/api/stats/', {
            'branch': 'master',
            'benchmark': benchmark.full_name,
        })

        self.assertEqual(len(response.data), 0)

        response = self.client.get('/api/stats/', {
            'benchmark': benchmark.full_name,
            'project': 'TheProject',
        })

        self.assertEqual(len(response.data), 0)

        response = self.client.get('/api/stats/', {
            'branch': 'master',
            'project': 'TheProject',
        })

        self.assertEqual(len(response.data), 0)

    @patch('django.conf.settings.IGNORE_GERRIT', False)
    def test_only_baseline_changes(self):

        now = timezone.now()
        yesterday = now - relativedelta(days=1)

        baseline = G(models.Result,
              manifest=MANIFEST(),
              branch_name='master',
              name="TheProject",
              created_at=yesterday,
              gerrit_change_number=None)

        patched = G(models.Result,
             manifest=MANIFEST(),
             branch_name='master',
             name="TheProject",
             created_at=now,
             gerrit_change_number=123)

        benchmark = G(models.Benchmark, group__name='/', name="TheBenchmark")
        environment = G(models.Environment, identifier='myenv')
        testjob_baseline = G(models.TestJob, id=u'888888', environment=environment,result=baseline, completed=True)
        testjob_patched = G(models.TestJob, id=u'999999', environment=environment, result=patched, completed=True)

        G(models.ResultData,
          result=baseline,
          benchmark=benchmark,
          test_job_id=testjob_baseline.id,
          name="TheBenchmark",
          measurement=5)

        G(models.ResultData,
          result=patched,
          benchmark=benchmark,
          test_job_id=testjob_patched.id,
          name="TheBenchmark",
          measurement=10)

        response = self.client.get('/api/stats/', {
            'branch': 'master',
            'benchmark': benchmark.full_name,
            'project': 'TheProject',
            'environment': 'myenv',
        })

        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['measurement'], 5)

    @patch('django.conf.settings.IGNORE_GERRIT', True)
    def test_only_baseline_changes_ignore_gerrit(self):

        now = timezone.now()
        yesterday = now - relativedelta(days=1)

        baseline = G(models.Result,
              manifest=MANIFEST(),
              branch_name='master',
              name="TheProject",
              created_at=yesterday,
              gerrit_change_number=None)

        patched = G(models.Result,
             manifest=MANIFEST(),
             branch_name='master',
             name="TheProject",
             created_at=now,
             gerrit_change_number=123)

        benchmark = G(models.Benchmark, group__name='foo/bar/', name="TheBenchmark")
        environment = G(models.Environment, identifier='myenv')
        testjob_baseline = G(models.TestJob, id=u'888888', environment=environment,result=baseline, completed=True)
        testjob_patched = G(models.TestJob, id=u'999999', environment=environment, result=patched, completed=True)

        G(models.ResultData,
          result=baseline,
          benchmark=benchmark,
          test_job_id=testjob_baseline.id,
          name="TheBenchmark",
          measurement=5)

        G(models.ResultData,
          result=patched,
          benchmark=benchmark,
          test_job_id=testjob_patched.id,
          name="TheBenchmark",
          measurement=10)

        response = self.client.get('/api/stats/', {
            'branch': 'master',
            'benchmark': benchmark.full_name,
            'project': 'TheProject',
            'environment': 'myenv',
        })

        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['measurement'], 10)
        self.assertEqual(response.data[1]['measurement'], 5)


class BenchmarkGroupSummaryTest(APITestCase):

    def setUp(self):
        user = User.objects.create_superuser('test', 'email@test.com', 'test')
        self.client.force_authenticate(user=user)

    def test_basic(self):
        result = G(models.Result, manifest=MANIFEST(), gerrit_change_number=None)
        group = G(models.BenchmarkGroup)
        env = G(models.Environment)
        G(models.BenchmarkGroupSummary, group=group, environment=env, result=result)
        response = self.client.get('/api/benchmark_group_summary/', {
            'benchmark_group': group.name,
            'environment': env.identifier,
            'branch': result.branch_name,
        })
        self.assertEqual(1, len(response.data))

    def test_returns_only_mainline_results(self):
        mainline_result = G(models.Result, manifest=MANIFEST(), branch_name='master', gerrit_change_number=None)
        patch_result = G(models.Result, manifest=MANIFEST(), branch_name='master', gerrit_change_number=999)
        group = G(models.BenchmarkGroup)
        env = G(models.Environment)
        G(models.BenchmarkGroupSummary, group=group, environment=env, result=mainline_result)
        G(models.BenchmarkGroupSummary, group=group, environment=env, result=patch_result)
        response = self.client.get('/api/benchmark_group_summary/', {
            'benchmark_group': group.name,
            'environment': env.identifier,
            'branch': 'master',
        })
        self.assertEqual(1, len(response.data))

class TestJobData(APITestCase):

    def setUp(self):
        self.testjob = G(
            models.TestJob,
            id="0001",
            status="Complete",
            completed=True,
            result__manifest=MANIFEST()
        )
        user = User.objects.create_superuser('test', 'email@test.com', 'test')
        self.client.force_authenticate(user=user)

    def test_download_json(self):
        self.testjob.data = get_file('now.json')
        self.testjob.save()

        response = self.client.get('/api/testjobdata/0001')
        self.assertEqual(200, response.status_code)
        self.assertEqual('application/json', response['Content-Type'])
        self.assertEqual('attachment; filename="0001.json"', response['Content-Disposition'])

    def test_data_filename_as_testjob_id(self):
        self.testjob.id = '0001.json'
        self.testjob.data = get_file('now.json')
        self.testjob.save()

        response = self.client.get('/api/testjobdata/0001.json')
        self.assertEqual(200, response.status_code)
        self.assertEqual('attachment; filename="0001.json"', response['Content-Disposition'])

    def test_download_xml(self):
        self.testjob.data = get_file('manifest.xml')
        self.testjob.save()

        response = self.client.get('/api/testjobdata/0001')
        self.assertEqual(200, response.status_code)
        self.assertEqual('application/xml', response['Content-Type'])

    @patch('mimetypes.guess_type', lambda filename: (None, None))
    def test_download_unknown_file_type(self):
        self.testjob.data = get_file('manifest.xml')
        self.testjob.save()

        response = self.client.get('/api/testjobdata/0001')
        self.assertEqual(200, response.status_code)
        self.assertEqual('application/octet-stream', response['Content-Type'])

    def test_requires_authentication(self):
        self.testjob.data = get_file('now.json')
        self.testjob.save()

        self.client.force_authenticate(user=None)

        response = self.client.get('/api/testjobdata/0001')
        self.assertEqual(401, response.status_code)


class ManifestDataTest(APITestCase):

    def setUp(self):
        user = User.objects.create_superuser('test', 'email@test.com', 'test')
        self.client.force_authenticate(user=user)

    def test_download_xml(self):
        m = G(models.Manifest, manifest=MINIMAL_XML)
        response = self.client.get('/api/manifest_data/%s/download/' % m.id)

        self.assertEqual(MINIMAL_XML, response.content)
        self.assertEqual('text/xml', response['Content-Type'])

        disposition = 'attachment; filename="%s.xml"' % m.manifest_hash
        self.assertEqual(disposition, response['Content-Disposition'])
