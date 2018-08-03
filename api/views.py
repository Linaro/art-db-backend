import json
import re
import urlparse
import mimetypes

mimetypes.init()

from itertools import groupby

from django.conf import settings
from django.db import transaction, IntegrityError
from django.db.models import Avg, StdDev, Count
from django.http import HttpResponse
from datetime import datetime
import time

from rest_framework import views
from rest_framework import viewsets
from rest_framework import response
from rest_framework import mixins
from rest_framework import status
from rest_framework import filters
from rest_framework.decorators import detail_route, api_view
from rest_framework.decorators import authentication_classes, permission_classes
from rest_framework.authtoken.models import Token
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import list_route

from benchmarks import models as benchmarks_models
from benchmarks.models import geomean
from benchmarks import tasks, testminer
from benchmarks import progress
from benchmarks import comparison

from . import serializers


# no statistics module in Python 2
def mean(data):
    n = len(data)
    if n < 1:
        return 0
    return sum(data)/float(n)


def _ss(data):
    c = mean(data)
    ss = sum((x-c)**2 for x in data)
    return ss


def stddev(data):
    n = len(data)
    if n < 2:
        return 0
    ss = _ss(data)
    pvar = ss/n
    return pvar**0.5


class TokenViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = (IsAuthenticated, )
    queryset = Token.objects.all()
    serializer_class = serializers.TokenSerializer

    def list(self, request, pk=None):
        serializer = self.serializer_class(Token.objects.get(user=request.user))
        return response.Response(serializer.data)


class ManifestViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [DjangoModelPermissions]
    queryset = (benchmarks_models.Manifest.objects
                .select_related("reduced")
                .prefetch_related("results"))

    serializer_class = serializers.ManifestSerializer

    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    search_fields = ('manifest_hash', 'reduced__hash')
    filter_fields = ('manifest_hash', 'reduced__hash')

class ManifestDataViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = benchmarks_models.Manifest.objects
    serializer_class = serializers.ManifestDataSerializer

    @detail_route()
    def download(self, request, pk=None):
        manifest = self.get_object()
        response = HttpResponse(manifest.manifest, content_type='text/xml')
        response['Content-Disposition'] = 'attachment; filename="%s.xml"' % manifest.manifest_hash
        return response

class ManifestReducedViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [DjangoModelPermissions]
    queryset = benchmarks_models.ManifestReduced.objects.prefetch_related("manifests__results")

    serializer_class = serializers.ManifestReducedSerializer


# benchmark
class BenchmarkViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, DjangoModelPermissions)
    queryset = benchmarks_models.Benchmark.objects.all().order_by('name').select_related('group')
    serializer_class = serializers.BenchmarkSerializer
    filter_fields = ('id', 'name')
    pagination_class = None


class BuildViewSet(viewsets.ModelViewSet):
    permission_classes = [DjangoModelPermissions]
    queryset = benchmarks_models.Result.objects.order_by('name').distinct('name')
    serializer_class = serializers.BuildSerializer
    pagination_class = None


class BranchViewSet(viewsets.ModelViewSet):
    permission_classes = [DjangoModelPermissions]
    queryset = benchmarks_models.Result.objects.order_by('branch_name').distinct('branch_name')
    serializer_class = serializers.BranchSerializer
    pagination_class = None


def get_limit(request):
    try:
        n = int(request.query_params.get('limit'))
    except (TypeError, ValueError):
        n = None
    if n < 0:
        n = None
    return n


def get_date_range(request):
    if get_limit(request):
        return None

    start = request.query_params.get('startDate')
    end = request.query_params.get('endDate')

    if start:
        date_range = { 'created_at__gt': datetime.fromtimestamp(float(start)) }
        if end:
            date_range['created_at__lt'] = datetime.fromtimestamp(float(end))
        return date_range
    else:
        return None


def get_benchmark_by_fullname(fullname):
    group = re.sub('[^/]*$', '', fullname)
    if not group:
        group = '/'
    name = re.sub('.*/', '', fullname)
    return benchmarks_models.Benchmark.objects.get(
        name=name,
        group__name=group
    )


class StatsViewSet(viewsets.ModelViewSet):
    queryset = (benchmarks_models.ResultData.objects
                .select_related("benchmark", "result")
                .order_by('created_at'))

    permission_classes = [DjangoModelPermissions]
    serializer_class = serializers.ResultDataSerializer
    pagination_class = None
    __queryset__ = None

    def get_queryset(self):
        if self.__queryset__:
            return self.__queryset__

        branch = self.request.query_params.get('branch')
        environment = self.request.query_params.get('environment')
        benchmark_fullnames = self.request.query_params.getlist('benchmark')

        benchmarks = [get_benchmark_by_fullname(b) for b in benchmark_fullnames]

        if not (benchmarks and branch and environment):
            return self.queryset.none()

        testjobs = benchmarks_models.TestJob.objects.filter(environment__identifier=environment)
        testjobs = testjobs.select_related('result')
        testjobs = testjobs.filter(result__branch_name=branch)

        if settings.IGNORE_GERRIT is False:
            testjobs = testjobs.filter(result__gerrit_change_number=None)

        testjob_ids = [ attrs['id'] for attrs in testjobs.values('id') ]

        n = get_limit(self.request)

        queryset = self.queryset.filter(
            test_job_id__in=testjob_ids,
            benchmark_id__in=[b.id for b in benchmarks]
        )

        dates = get_date_range(self.request)
        if dates:
            queryset = queryset.filter(**dates)

        self.__queryset__ = queryset.order_by('-created_at')[:n]
        return self.__queryset__


class BenchmarkGroupSummaryViewSet(viewsets.ModelViewSet):
    queryset = benchmarks_models.BenchmarkGroupSummary.objects.filter(result__gerrit_change_number=None).order_by('created_at')
    permission_classes = [DjangoModelPermissions]
    serializer_class = serializers.BenchmarkGroupSummarySerializer
    pagination_class = None

    def get_queryset(self):
        group = self.request.query_params.get('benchmark_group')
        env = self.request.query_params.get('environment')
        branch = self.request.query_params.get('branch')

        n = get_limit(self.request)

        queryset = self.queryset.filter(
            environment__identifier=env,
            group__name=group,
            result__branch_name=branch,
        ).order_by('-created_at')

        dates = get_date_range(self.request)
        if dates:
            queryset = queryset.filter(**dates)

        return queryset[:n]


@api_view(["GET"])
def dynamic_benchmark_summary(request):
    branch = request.query_params.get('branch')
    environment = request.query_params.get('environment')
    benchmark_fullnames = request.query_params.getlist('benchmarks')

    benchmarks = [get_benchmark_by_fullname(b) for b in benchmark_fullnames]

    testjobs = benchmarks_models.TestJob.objects.filter(environment__identifier=environment)
    testjobs = testjobs.select_related('result')
    testjobs = testjobs.filter(result__branch_name=branch)
    if settings.IGNORE_GERRIT is False:
        testjobs = testjobs.filter(result__gerrit_change_number=None)

    testjob_ids = [ attrs['id'] for attrs in testjobs.values('id') ]

    n = get_limit(request)

    queryset = (benchmarks_models.ResultData.objects
                .select_related("benchmark", "result")
                .filter(
                    test_job_id__in=testjob_ids,
                    benchmark_id__in=[b.id for b in benchmarks],
                )
                .order_by('-created_at'))

    dates = get_date_range(request)
    if dates:
        queryset = queryset.filter(**dates)

    if n:
        n = n * len(benchmarks)
        queryset = queryset[:n]

    data = []
    for result_id, result_data in groupby(queryset, lambda rd: rd.result_id):
        values = []
        for r in result_data:
            created_at = r.created_at
            values = values + r.values
        data.append({
            'result': result_id,
            'created_at': created_at.isoformat(),
            'measurement': geomean(values),
            'name': 'Summary',
        })

    response = HttpResponse(json.dumps(data), content_type='application/json')
    return response


@api_view(["GET"])
def annotations(request):
    results = benchmarks_models.Result.objects.exclude(annotation=None)
    dates = get_date_range(request)
    if dates:
        results = results.filter(**dates)

    limit = get_limit(request)
    if limit:
        results = results[:limit]

    data = []
    for r in results.values('created_at', 'annotation'):
        r['date'] = r.pop('created_at').isoformat()
        r['label'] = r.pop('annotation')
        data.append(r)

    response = HttpResponse(json.dumps(data), content_type='application/json')
    return response


@api_view(["POST"])
@authentication_classes((SessionAuthentication,))
@permission_classes((IsAuthenticated,))
def save_annotation(request, build_id):
    result = benchmarks_models.Result.objects.get(pk=build_id)
    result.annotation = request.data.get("annotation")
    result.save()
    return HttpResponse('OK')


# result
class ResultViewSet(viewsets.ModelViewSet):
    permission_classes = [DjangoModelPermissions]
    queryset = (benchmarks_models.Result.objects
                .select_related('manifest')
                .prefetch_related('test_jobs'))
    serializer_class = serializers.ResultSerializer

    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    search_fields = ('branch_name',
                     'name',
                     'build_id',
                     'gerrit_change_number',
                     'gerrit_patchset_number',
                     'gerrit_change_url',
                     'gerrit_change_id',
                     'manifest__manifest_hash',
                     'manifest__reduced__hash')
    filter_fields = ('branch_name',
                     'name',
                     'build_id',
                     'gerrit_change_number',
                     'gerrit_patchset_number',
                     'gerrit_change_url',
                     'gerrit_change_id',
                     'manifest__manifest_hash',
                     'manifest__reduced__hash')

    @detail_route()
    def baseline(self, request, pk=None):
        result = self.get_object()
        if not result.baseline:
            return response.Response(status=status.HTTP_204_NO_CONTENT)

        serializer = self.serializer_class(result.baseline)
        return response.Response(serializer.data)

    @detail_route()
    def benchmarks(self, request, pk=None):
        result = self.get_object()
        test_jobs = result.test_jobs.prefetch_related('environment').all()
        result_data = result.data.prefetch_related('benchmark').all()

        data = []
        for test_job in test_jobs:
            rdata = [ r for r in result_data if r.test_job_id == test_job.id ]
            data.append({
                "environment": test_job.environment and test_job.environment.identifier,
                "data": serializers.ResultDataSerializer(rdata, many=True).data
            })

        return response.Response(data)

    @detail_route()
    def benchmarks_compare(self, request, pk=None):
        result = self.get_object()
        comparison_base = request.query_params.get('comparison_base')
        if comparison_base:
            previous = benchmarks_models.Result.objects.get(pk=comparison_base)
        else:
            previous = result.to_compare()
        if not previous:
            return response.Response([])

        def __get_key(item):
            return item['change']

        data = []
        for item in progress.get_progress_between_results(result, previous):
            data_list = []
            for data_item in comparison.compare(item.before, item.after):
                data_list.append({
                    'change': data_item['change'],
                    'current': serializers.ResultDataSerializer(
                        data_item['current']).data,
                    'previous': serializers.ResultDataSerializer(
                        data_item['previous']).data,
                })
            res = {
                "environment": item.environment.identifier,
                "data": sorted(data_list, reverse=True, key=__get_key)
            }
            data.append(res)

        return response.Response(data)

    def create(self, request, *args, **kwargs):
        attempts = 0
        while True:
            try:
                return self.__create__(request, *args, **kwargs)
            except IntegrityError:
                attempts = attempts + 1
                time.sleep(0.5)
                if attempts >= 10:
                    raise

    @transaction.atomic
    def __create__(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        delayed_tasks = []

        try:
            result = benchmarks_models.Result.objects.get(
                build_id=serializer.initial_data['build_id'],
                name=serializer.initial_data['name']
            )
            if not serializer.is_valid():
                serializer = self.get_serializer(instance=result, data=request.data)
                serializer.is_valid()
        except benchmarks_models.Result.DoesNotExist:
            serializer.is_valid(raise_exception=True)
            result = serializer.save()

        if request.data.get('test_jobs'):

            test_jobs = {item.strip() for item in request.data.get('test_jobs').split(",")}

            for testjob_id in test_jobs:
                if len(testjob_id) > 0:
                    testjob, testjob_created = benchmarks_models.TestJob.objects.get_or_create(
                        result=result,
                        id=testjob_id
                    )
                    if testjob_created:
                        delayed_tasks.append((tasks.set_testjob_results, [testjob_id]))
            delayed_tasks.append((tasks.update_jenkins, [result]))
        else:
            # no test_jobs, expect *.json to be passed in directly
            for filename in request.FILES:
                if not filename.endswith('.json'):
                    next
                env = re.sub('.json$', '', filename)
                filedata = request.FILES[filename]

                self.__create_test_job__(result, env, filedata)

        # all done, schedule background tasks
        for task, args in delayed_tasks:
            task.apply_async(args=args, countdown=60) # 1 min from now

        return response.Response(serializer.data, status=status.HTTP_201_CREATED)

    def __create_test_job__(self, result, env, data):
        environment, _ = benchmarks_models.Environment.objects.get_or_create(identifier=env)
        spl = urlparse.urlsplit(result.build_url)
        runnerurl = "%s://%s/job/%s/%s/" % (spl.scheme, spl.netloc, result.name, result.build_number)
        testjob = benchmarks_models.TestJob.objects.create(
            id='J' + str(result.build_id) + '_' + result.name + '_' + env,
            result=result,
            status='Complete',
            initialized=True,
            completed=True,
            data=data,
            testrunnerclass='ArtJenkinsTestResults',
            testrunnerurl=runnerurl,
            environment=environment,
            created_at=result.created_at,
        )
        testrunner = testjob.get_tester()
        json_data = testjob.data.read()
        test_results = testrunner.parse_test_results(json_data)
        tasks.store_testjob_data(testjob, test_results)


class TestJobViewSet(viewsets.ModelViewSet):
    permission_classes = [DjangoModelPermissions]
    queryset = benchmarks_models.TestJob.objects.all()
    serializer_class = serializers.TestJobSerializer

    lookup_value_regex = "[^/]+"  # LAVA ids are 000.0

    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    filter_fields = ('result',
                     'initialized',
                     'completed',
                     'testrunnerclass',
                     'status')
    search_fields = ('id',
                     'name')

    @detail_route()
    def resubmit(self, request, pk=None):
        # fixme: this should not happen on GET

        forbidden_statuses = ['Complete', 'Running', 'Submitted', '']

        testjob = self.get_object()

        if testjob.status in forbidden_statuses or\
                testjob.resubmitted:

            serializer = serializers.TestJobSerializer(testjob.result.test_jobs.all(), many=True)
            return response.Response(serializer.data, status=status.HTTP_400_BAD_REQUEST)

        netloc = urlparse.urlsplit(testjob.testrunnerurl).netloc
        username, password = settings.CREDENTIALS[netloc]
        tester = (getattr(testminer, testjob.testrunnerclass)
                  (testjob.testrunnerurl, username, password))

        testjobs = tester.call_xmlrpc('scheduler.resubmit_job', testjob.id)
        result = testjob.result

        testjob.resubmitted = True
        testjob.save()

        if not isinstance(testjobs, (list, tuple)):
            testjobs = [testjobs]

        for testjob_id in testjobs:
            testjob = benchmarks_models.TestJob.objects.create(
                result=result,
                id=testjob_id
            )
            tasks.set_testjob_results.apply(args=[testjob])

        serializer = serializers.TestJobSerializer(result.test_jobs.all(), many=True)

        return response.Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def download_testjob_data(request, testjob_id):
    testjob = benchmarks_models.TestJob.objects.get(pk=testjob_id)

    content_type, _ = mimetypes.guess_type(testjob.data.path)
    data = testjob.data.read()

    if testjob.id.endswith('.' + testjob.data_filetype):
        filename = testjob.id
    else:
        filename = testjob.id + '.' + testjob.data_filetype

    if content_type is None:
        content_type = 'application/octet-stream'

    response = HttpResponse(data, content_type=content_type)
    response['Content-Disposition'] = 'attachment; filename="%s"' % filename
    return response


class ResultDataViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAuthenticated, DjangoModelPermissions)
    queryset = benchmarks_models.ResultData.objects.all()
    serializer_class = serializers.ResultDataSerializer
    filter_fields = ('id',
                     'benchmark',
                     'name',
                     'result',
                     'created_at')


class ResultDataForManifest(views.APIView):
    """
    Class for showing all results for set parameters:
     - manifest
     - gerrit change ID/number/patchset
    """
    def get_queryset(self):
        queryset = benchmarks_models.ResultData.objects.all()
        manifest = self.request.query_params.get('manifest_id', None)
        gerrit_change_id = self.request.query_params.get('gerrit_change_id', None)
        gerrit_change_number = self.request.query_params.get('gerrit_change_number', None)
        gerrit_patchset_number = self.request.query_params.get('gerrit_patchset_number', None)

        print manifest
        print gerrit_change_id
        print gerrit_change_number
        print gerrit_patchset_number

        results = benchmarks_models.Result.objects.all()
        if manifest:
            results = results.filter(manifest__id=manifest)
        if gerrit_change_id:
            results = results.filter(gerrit_change_id=gerrit_change_id)
        results = results.filter(gerrit_change_number=gerrit_change_number)
        results = results.filter(gerrit_patchset_number=gerrit_patchset_number)
        if gerrit_change_number is None \
            and gerrit_patchset_number is None \
            and gerrit_change_id is None \
            and manifest is None:
            # get results for latest available manifest baseline
            manifest = benchmarks_models.Manifest.objects.latest("id").pk
            results = results.filter(manifest__id=manifest)

        # All result data that matches manifest and/or gerrit
        queryset = queryset.filter(result__in=results)
        print queryset.all()
        return queryset

    def get(self, request, format=None):
        results = []
        metadata = {}
        ret = {
            "data": results,
            "metadata": metadata
        }
        queryset = self.get_queryset()
        results_objects = benchmarks_models.Result.objects.filter(data__in=queryset)
        branches = results_objects.values_list("branch__name").distinct()
        if len(branches) == 1:
            # there should be only one
            metadata['branch'] = branches[0][0]
        manifests = results_objects.values_list("manifest__id").distinct()
        if len(manifests) == 1:
            # there should be only one
            metadata['manifest'] = manifests[0][0]
        boards = results_objects.values_list("board__displayname").distinct()
        metadata['boards'] = [x[0] for x in boards]
        build_urls = results_objects.values_list("build_url").distinct()
        metadata['builds'] = [x[0] for x in build_urls]

        gerrit_change_numbers = results_objects.values_list("gerrit_change_number").distinct()
        gerrit_patchset_numbers = results_objects.values_list("gerrit_patchset_number").distinct()
        if len(gerrit_patchset_numbers) == 1 and \
            len(gerrit_change_numbers) == 1:
                if gerrit_patchset_numbers[0][0] is not None and \
                    gerrit_change_numbers[0][0] is not None:
                    metadata['gerrit'] = "%s/%s" % (gerrit_change_numbers[0][0], gerrit_patchset_numbers[0][0])

        benchmark_name_list = queryset.values_list('benchmark__name').distinct()
        for benchmark in benchmark_name_list:
            res_list = queryset.filter(benchmark__name=benchmark[0])
            subscore_name_list = res_list.values_list('name').distinct()
            for subscore in subscore_name_list:
                s = res_list.filter(name=subscore[0])
                avg = s.aggregate(Avg('measurement'))
                stddev = s.aggregate(StdDev('measurement'))
                length = s.aggregate(Count('measurement'))
                subscore_dict = {
                    'benchmark': benchmark[0],
                    'subscore': subscore[0]
                    }
                subscore_dict.update(avg)
                subscore_dict.update(stddev)
                subscore_dict.update(length)
                results.append(subscore_dict)
        return response.Response(ret)


class SettingsViewSet(viewsets.ViewSet):
    @list_route()
    def manifest_settings(self, query):
        return response.Response(settings.BENCHMARK_MANIFEST_PROJECT_LIST)


class ProjectsView(views.APIView):
    # lists all project names in Result objects
    def get_queryset(self):
        queryset = benchmarks_models.Result.objects.all()
        if not settings.IGNORE_GERRIT:
            # restrict to the baslines build projects
            queryset = queryset.filter(gerrit_change_number=None)
        return queryset.order_by("name").distinct("name")

    def get(self, request):
        return response.Response(self.get_queryset().values("name"))


class EnvironmentsView(views.APIView):
    def get_queryset(self):
        return benchmarks_models.Environment.objects.all().order_by('identifier')

    def get(self, request):
        return response.Response(self.get_queryset().values("identifier", "name"))


