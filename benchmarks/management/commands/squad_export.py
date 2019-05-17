# -*- coding: utf-8 -*-
import json
import os
import re
import shutil
import sys
from django.core.management.base import BaseCommand


from benchmarks.models import Result

# mapping ART-reports → squad:
# Result → Build
# TestJob → TestRun
# ResultData → Metric

class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'outputdir',
            help='Output directory',
        )

        parser.add_argument(
            '--aggressive-grouping',
            action='store_true',
            dest='aggressive_grouping',
            help='Be more aggressive when translating benchmark names intro groups'
        )

    def handle(self, *args, **options):
        self.options = options
        total = Result.objects.count()
        c = 0
        for result in Result.objects.all():
            self.export(result, options['outputdir'])
            c += 1
            print('Processed build %d/%d' % (c, total))

    def export(self, result, directory):
        build_id = result.manifest.reduced_id
        builddir = os.path.join(directory, result.name, build_id)
        for testjob in result.test_jobs.all():
            self.export_testjob(testjob, builddir)

    def export_testjob(self, testjob, directory):
        if not testjob.environment:
            return

        jobdir = os.path.join(directory, testjob.environment.identifier, testjob.id)

        metrics = {}
        for data in testjob.result_data.all():
            if self.options['aggressive_grouping']:
                key = re.sub('\.', '/', data.benchmark.name)
                if key != data.benchmark.name:
                    key += '.' + data.name
                else:
                    key += '/' + data.name
            else:
                key = data.benchmark.name + '.' + data.name
            if data.benchmark.group:
                # ...group.name is garanteed to end with a slash
                key = data.benchmark.group.name + key
            metrics[key] = data.values
        if metrics:
            metadata = {
                'datetime': testjob.created_at.isoformat(),
                'job_id': testjob.id,
                'job_status': testjob.status,
                'job_url': testjob.url ,
                'build_url': testjob.result.build_url,
            }

            os.makedirs(jobdir, exist_ok=True)
            with open(os.path.join(jobdir, 'metrics.json'), 'w') as f:
                f.write(json.dumps(metrics, indent=4))
            with open(os.path.join(jobdir, 'metadata.json'), 'w') as f:
                f.write(json.dumps(metadata, indent=4))
        if testjob.data:
            os.makedirs(jobdir, exist_ok=True)
            filename = testjob.data.file.name
            shutil.copy2(filename, os.path.join(jobdir, os.path.basename(filename)))
