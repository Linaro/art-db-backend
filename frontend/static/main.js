var app = angular.module('art', ['ngRoute', 'ngMaterial']);

app.controller('Toolbar', ['$scope', '$http', '$rootScope', function($scope, $http, $rootScope) {

    $rootScope.$on( "$routeChangeSuccess", function(event, next, current) {
        $scope.viewName = next.$$route ? next.$$route.controller : '';
    });

    $http.get('/api/token/').then(function(response) {
        $scope.auth = response.data;
    });

    $scope.show_user_dropdown = false;

    $scope.toggle_user_dropdown = function() {
        $scope.show_user_dropdown = !$scope.show_user_dropdown;
        var dropdown = document.getElementById('user-dropdown-menu');
        if ($scope.show_user_dropdown) {
            dropdown.style.display = 'block';
        } else {
            dropdown.style.display = '';
        }
    }

}]);

app.config(['$routeProvider', function($routeProvider) {
    $routeProvider
        .when('/builds/', {
            templateUrl: '/static/templates/build_list.html',
            controller: 'BuildList',
            reloadOnSearch: false
        })
        .when('/builds/compare/', {
            templateUrl: '/static/templates/compare.html',
            controller: 'CompareBuilds',
            reloadOnSearch: false
        })
        .when('/build/:buildId', {
            templateUrl: '/static/templates/build_detail.html',
            controller: 'BuildDetail',
            reloadOnSearch: false
        })
        .when('/manifests/', {
            templateUrl: '/static/templates/manifest_list.html',
            controller: 'ManifestList',
            reloadOnSearch: false
        })
        .when('/manifests/reduced/', {
            templateUrl: '/static/templates/manifest_reduced_list.html',
            controller: 'ManifestReducedList',
            reloadOnSearch: false
        })
        .when('/stats/', {
            templateUrl: '/static/templates/stats.html',
            controller: 'Stats',
            reloadOnSearch: false
        })
        .otherwise({
            redirectTo: '/stats/'
        });
}]);


app.config(['$httpProvider', function($httpProvider) {
    $httpProvider.defaults.xsrfCookieName = 'csrftoken';
    $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';
}])

app.directive('pagination', ['$route', '$httpParamSerializer', '$location', function($route, $httpParamSerializer, $location) {
    return {
        restrict: 'E',
        scope: {
            page: '='
        },
        templateUrl: '/static/templates/_pagination.html',
        link: function(scope, elem, attrs) {

            scope.goNext = function() {
                $location.search("page", scope.page.page.next);
                $route.reload();
            };

            scope.goBack = function() {
                $location.search("page", scope.page.page.previous);
                $route.reload();
            };
        }
    };
}]);


app.controller(
    'ManifestList',

    ['$scope', '$http', '$routeParams', '$location',

     function($scope, $http, $routeParams, $location) {

         var params = {
             'search': $routeParams.search,
             'page': $routeParams.page
         };

         $http.get('/api/manifest/', {params: params}).then(function(response) {
             $scope.page = response.data;
         });

         $scope.search = $routeParams.search;

         $scope.makeSearch = function() {
             $location.search({'search': $scope.search || null});

             $http.get('/api/manifest/', {params: {'search': $scope.search}})
                 .then(function(response) {
                     $scope.page = response.data;
                 });
         };
     }]
);

app.controller(
    'ManifestReducedList',

    ['$scope', '$http', '$routeParams', '$location',

     function($scope, $http, $routeParams, $location) {

         var params = {
             'search': $routeParams.search,
             'page': $routeParams.page
         };

         $http.get('/api/manifest_reduced/', {params: params}).then(function(response) {
             $scope.page = response.data;
         });

         $http.get('/api/settings/manifest_settings/').then(function(response) {
             $scope.settings = response.data;
         });

         $scope.search = $routeParams.search;

         $scope.makeSearch = function() {
             $location.search({'search': $scope.search || null});

             $http.get('/api/manifest_reduced/', {params: {'search': $scope.search}})
                 .then(function(response) {
                     $scope.page = response.data;
                 });
         };
     }]
);

function count_by_status(test_jobs) {
    var data = {};
    _.each(test_jobs, function(t) {
        var st = t.status;
        if (data[st]) {
            data[st] += 1;
        } else {
            data[st] = 1
        }
    });

    var text = _.map(data, function(count, st) {
        return st + ': ' + count;
    })

    return _.join(text, '<br/>');
}


app.controller(
    'BuildList',

    ['$scope', '$http', '$routeParams', '$location', '$sce',

     function($scope, $http, $routeParams, $location, $sce) {

         var params = {
             'search': $routeParams.search,
             'page': $routeParams.page
         };

         $http.get('/api/result/', {params: params}).then(function(response) {
             $scope.page = response.data;
             _.each($scope.page.results, function(build) {
                 build.test_jobs_count_by_status = $sce.trustAsHtml(count_by_status(build.test_jobs));
             })
         });

         $scope.search = $routeParams.search;

         $scope.makeSearch = function() {
             $location.search({'search': $scope.search || null});

             $http.get('/api/result/', {params: {'search': $scope.search}})
                 .then(function(response) {
                     $scope.page = response.data;
                 });
         };


         $scope.setCompareFrom = function(id) {
             $scope.compareFrom = id;
             return true;
         }

         $scope.setCompareTo = function(id) {
             if (id == $scope.compareFrom) {
                 return false;
             } else {
                 $scope.compareTo = id;
                 return true;
             }
         }

         $scope.compare = function() {
             if (!($scope.compareFrom && $scope.compareTo)) {
                 alert('Please select builds to compare first');
                 return;
             }
             location.href = '#/builds/compare/?from=' + $scope.compareFrom + '&to=' + $scope.compareTo;
         }
     }]
);

app.controller('BuildDetail', ['$scope', '$http', '$routeParams', '$q', '$routeParams', '$location', function($scope, $http, $routeParams, $q, $routeParams, $location) {

    $scope.queryBenchmarks = $routeParams.benchmarks || "";

    $scope.isEmpty = _.isEmpty;

    $q.all([
        $http.get('/api/result/' + $routeParams.buildId + '/'),
        $http.get('/api/result/' + $routeParams.buildId + '/benchmarks/'),
        $http.get('/api/result/' + $routeParams.buildId + '/baseline/')
    ]).then(function(response) {
        $scope.error = null;
        $scope.build = response[0].data;
        $scope.benchmarks = response[1].data;
        $scope.baseline = response[2].data;
    }).catch(function(error) {
        $scope.error = error;
    });

    $scope.resubmit = function(testJob) {
        testJob.refresh = false;
        $scope.testJobUpdate = true;
        $http.get('/api/testjob/' + testJob.id + '/resubmit/').then(function(response) {
            $scope.build.test_jobs = response.data;
            $scope.testJobUpdate = false;
        });
    };

    $scope.filterBenchmarks = function(criteria) {
        $location.search({'benchmarks': criteria || null});

        return function(item) {
            if (!criteria) {
                return true;
            }
            if (item.benchmark.toLowerCase().indexOf(criteria.toLowerCase()) != -1 ||
                item.name.toLowerCase().indexOf(criteria.toLowerCase()) != -1) {
                return true;
            }
            return false;
        };
    };

    $scope.saving = false
    $scope.save_annotation = function() {
        $scope.saving = true
        if ($scope.build.annotation && $scope.build.annotation.trim() == '') {
            $scope.build.annotation = null
        }
        $http.post(
            '/api/saveannotation/' + $scope.build.id + '/',
            { annotation: $scope.build.annotation }
        ).then(function() {
            $scope.edit = false
            $scope.saving = false
        })
    };
    $scope.delete_annotation = function() {
        $scope.build.annotation = null;
        $scope.save_annotation()
    }

}]);

app.controller('CompareBuilds', ['$scope', '$http', '$routeParams', '$q', '$routeParams', '$location', function($scope, $http, $routeParams, $q, $routeParams, $location) {

    $scope.filterBenchmarksCompared = function(criteria) {
        $location.search('benchmarks', criteria || null);

        return function( item ) {
            if (!criteria) {
                return true;
            }
            if (item.current.benchmark.toLowerCase().indexOf(criteria.toLowerCase()) != -1 ||
                item.current.name.toLowerCase().indexOf(criteria.toLowerCase()) != -1) {
                return true;
            }
            return false;
        };
    };

    $scope.getChangeClass = function(criteria) {
        if (criteria < -3) {
            return "success";
        }
        if (criteria >= -3 && criteria <= 3) {
            return "";
        }
        if (criteria > 3) {
            return "danger";
        }
    }

    $scope.compare = function(ev) {
        if (ev && ev.keyCode != 13) {
            return;
        }

        if (!($scope.compareFrom && $scope.compareTo)) {
            alert('Please inform the build numbers to compare');
            return;
        }
        $location.search({'from': $scope.compareFrom, 'to': $scope.compareTo});
        $scope.loading = true;
        $scope.ready = false;
        $scope.error = null;
        $q.all([
            $http.get('/api/result/' + $scope.compareFrom + '/'),
            $http.get('/api/result/' + $scope.compareTo + '/'),
            $http.get('/api/result/' + $scope.compareTo + '/benchmarks_compare/?comparison_base=' + $scope.compareFrom),
        ]).then(function (response) {
            $scope.ready = true;
            $scope.buildFrom = response[0].data;
            $scope.buildTo = response[1].data;
            $scope.comparisons = response[2].data;
        }).catch(function(error) {
            $scope.error = error;
        });
    }
    if ($routeParams.from && $routeParams.to) {
        $scope.compareFrom = $routeParams.from;
        $scope.compareTo = $routeParams.to;
        $scope.compare();
    } else {
        $location.search({});
    }

}]);


function forceArray(obj) {
    if (obj) {
      if (Array.isArray(obj)) {
          return obj;
      } else {
          return [obj];
      }
    } else {
        return [];
    }
}

function slug(s) {
    return s.toLowerCase().replace(/\W+/g, '-').replace(/-$/, '');
}

function getChartId(benchmark) {
    var id = slug(benchmark.full_name);
    return 'chart-' + id;
}

app.controller('Stats', ['$scope', '$http', '$routeParams', '$timeout', '$q', '$routeParams', '$location', function($scope, $http, $routeParams, $timeout, $q, $routeParams, $location) {

    $scope.get_environment_ids = function() {
        var selected = _.filter($scope.environments, function(env) { return env.selected });
        return _.map(selected, function(env) { return env.identifier} );
    }

    $scope.change = function() {
        for (var i = 0; i < $scope.benchmarks.length; i++) {
            $scope.benchmarks[i].graphed = false;
        }
        $scope.updateCharts();
    }

    $scope.updateCharts = function() {

        $scope.disabled = true;

        if (($scope.limit != -100) || ($scope.limit == -100 && $scope.startDate)) {
            for (var i = 0; i < $scope.benchmarks.length; i++) {
                var benchmark = $scope.benchmarks[i];

                // skip benchmarks that were already graphed
                if (benchmark.graphed) {
                    continue;
                }

                var charts = document.getElementById('charts');
                var this_chart_id = getChartId(benchmark);
                var this_chart = document.getElementById(this_chart_id);
                if (!this_chart) {
                    this_chart = document.createElement('div');
                    this_chart.className = 'chart panel panel-default';
                    this_chart.id = this_chart_id;
                    charts.appendChild(this_chart);
                }

                var params = {
                    branch: $scope.branch.branch_name,
                    environment: $scope.get_environment_ids(),
                    startDate: $scope.startDate && $scope.startDate.getTime() / 1000,
                    endDate: $scope.endDate && $scope.endDate.getTime() / 1000,
                    limit: $scope.limit
                };

                if (params.environment.length > 0) {
                    this_chart.innerHTML = '<i class="fa fa-cog fa-spin"></i>';
                } else {
                    this_chart.innerHTML = '<div class="alert alert-warning"><i class="fa fa-info-circle"></i>No data to chart. Select at least 1 environment.</div>';
                }

                var stats_endpoint;
                if (benchmark.type == 'benchmark_group' || benchmark.type == 'root_benchmark_group') {
                    stats_endpoint = '/api/benchmark_group_summary/';
                    params.benchmark_group = benchmark.name;
                } else if (benchmark.type == 'dynamic_benchmark_summary') {

                    var selected = _.filter($scope.benchmarks, function(benchmark) {
                        return benchmark.type == 'benchmark';
                    });
                    params.summary = 1;

                    if (selected.length > 0) {
                        /* if there are any benckmarks selected, we'll get a
                         * dynamically-calculated summary of them
                         */
                        stats_endpoint = '/api/dynamic_benchmark_summary/';
                        params.benchmarks = _.map(selected, function(benchmark) {
                            return benchmark.full_name;
                        })
                        $scope.dynamic_benchmark_summary.label = "Summary of selected benchmarks";

                        this_chart.title = 'Summary of: ' + _.join(_.map(selected, function(b) { return b.name} ), ', ');

                    } else {
                        /* no benchmarks selected: just display the overall summary
                         * instead
                         */
                        stats_endpoint = '/api/benchmark_group_summary/';
                        params.benchmark_group = '/';
                        $scope.dynamic_benchmark_summary.label = "Summary of all benchmarks";
                    }
                }
                else {
                    stats_endpoint = '/api/stats/';
                    params.benchmark = benchmark.full_name;
                }

                $q.all(_.map($scope.get_environment_ids(), function(env) {
                    var env_params = {};
                    _.each(params, function(v, k) {
                        env_params[k] = v;
                    });
                    env_params.environment = env;
                    return $http.get(stats_endpoint, { params: env_params });
                })).then(function(data_by_env) {
                    var bname;
                    if (data_by_env[0].config.params.summary) {
                        bname = ':summary:';
                    } else {
                        bname = data_by_env[0].config.params.benchmark ||
                            data_by_env[0].config.params.benchmark_group;
                    }

                    var benchmark = _.find($scope.benchmarks, ['full_name', bname]);
                    var target_id = getChartId(benchmark);
                    var target = document.getElementById(target_id);

                    $http.get('/api/annotations/', { params: params }).then(function(response) {
                        var annotations = _.map(response.data, function(item) {
                            return {
                                x: Date.parse(item.date),
                                label: item.label
                            }
                        })
                        $scope.drawChart(benchmark, $scope.branch, data_by_env, annotations, target);
                        benchmark.graphed = true;
                    })
                });
            }
        }

        $location.search({
            branch: $scope.branch.branch_name,
            environment: $scope.get_environment_ids(),
            benchmark: _.map($scope.benchmarks, 'full_name'),
            startDate: $scope.startDate && $scope.startDate.getTime() / 1000,
            endDate: $scope.endDate && $scope.endDate.getTime() / 1000,
            limit: $scope.limit
        });

        $scope.disabled = false;
    };

    $scope.addBenchmark = function() {
        var benchmark = $scope.benchmark;
        if (! _.find($scope.benchmarks, benchmark)) {
            $scope.benchmarks.push(benchmark);
            if (benchmark.type == 'benchmark') {
                $scope.dynamic_benchmark_summary.graphed = false;
            }
            $scope.updateCharts();
        }
        $scope.benchmark = undefined;
    }

    $scope.removeBenchmark = function(benchmark) {
        var id = getChartId(benchmark);
        document.getElementById(id).remove();
        _.remove($scope.benchmarks, benchmark);
        benchmark.graphed = false;
        if (benchmark.type == 'benchmark') {
            $scope.dynamic_benchmark_summary.graphed = false;
        }
        $scope.updateCharts();
    }

    $scope.drawChart = function(benchmark, branch, env_data, annotations, element) {
        var series = [];
        var i = -1;

        var plotLines = _.map(annotations, function(item) {
            return {
                color: '#babdb6',
                width: 0.5,
                value: item.x,
                label: {
                    rotation: 90,
                    align: 'right',
                    textAlign: 'left',
                    text: item.label
                }
            }
        })

        _.each(env_data, function(response) {

            var env = response.config.params.environment;

            _.each(_.groupBy(response.data, "name"), function(data, name) {

                i++;

                // data itself
                series.push({
                    name: name + ' (' + env + ')',
                    type: 'spline',
                    color: Highcharts.getOptions().colors[i],
                    zIndex: 1,
                    data: _.map(data, function(point) {
                        return {
                            x: Date.parse(point.created_at),
                            y: point.measurement,
                            min: _.min(point.values),
                            max: _.max(point.values),
                            result_id: point.result,
                        };
                    })
                });

                if (data[0].values == undefined) {
                    // data does not have multiple values, skip the range
                    // data series
                    return;
                }

                // range of values, based on the standard deviation
                series.push({
                    name: name + ' range (' + env + ')',
                    type: 'areasplinerange',
                    color: Highcharts.getOptions().colors[i],
                    lineWidth: 0,
                    linkedTo: ':previous',
                    fillOpacity: 0.3,
                    zIndex: 0,
                    data: _.map(data, function(point) {
                        return [
                            Date.parse(point.created_at),
                            _.min(point.values),
                            _.max(point.values)
                        ]
                    })
                });

            });
        });

        Highcharts.chart(
                element, {
                    chart: {
                        zoomType: "xy"
                    },
                    title: {
                        text: (benchmark.type == 'benchmark' && benchmark.full_name || benchmark.label) + ' on branch ' + branch.branch_name
                    },
                    xAxis: {
                        type: 'datetime',
                        dateTimeLabelFormats: {
                            month: '%e. %b',
                            year: '%b'
                        },
                        plotLines: plotLines,
                        title: {
                            text: 'Date'
                        }
                    },
                    tooltip: {
                        useHTML: true,
                        pointFormatter: function() {
                            if (this.series.type == 'areasplinerange') {
                                return '';
                            }
                            var y = this.y.toFixed(2);
                            var min = this.min && this.min.toFixed(2);
                            var max = this.max && this.max.toFixed(2);
                            var range = '';
                            if (this.min && this.max) {
                                range = _.join([
                                        '<br/>',
                                        'Range: ',
                                        this.min.toFixed(2),
                                        ' — ',
                                        this.max.toFixed(2)
                                ], '');
                            }
                            var html = [
                                '<br/><p><em>',
                                '<span style="color: ' + this.series.color + '">' + this.series.name + '</span></em><br/> ',
                                '<strong>',
                            'Mean: ' + y,
                            '</strong>',
                            range,
                            '</p>',
                            '<p>',
                            '<a href="#/build/' + this.result_id + '">See details for build #' + this.result_id + '</a>',
                            '</p>'
                            ]
                            return _.join(html, '');
                        }
                    },
                    plotOptions: {
                        series: {
                            cursor: 'pointer',
                            point: {
                                events: {
                                    click: function (e) {
                                        location.href = '#/build/' + this.result_id;
                                    }
                                }
                            },
                            marker: {
                                lineWidth: 1
                            }
                        }
                    },
                    legend: {
                        maxHeight: 100
                    },
                    series: series
                });
    }

    $scope.toggleEnvironments = function(v) {
        _.each($scope.environments, function(env) {
            env.selected = v;
        });
        $scope.change();
    }

    $scope.reset = function() {
        $scope.branch = undefined;
        _.each($scope.environments, function(env) {
            env.selected = false;
        });
        $scope.benchmark = undefined;
        $location.search({});
        document.getElementById('charts').innerHTML = '';
    }

    $q.all([
        $http.get('/api/branch/'),
        $http.get('/api/benchmark/'),
        $http.get('/api/environments/')
    ]).then(function(response) {

        $scope.branchList = response[0].data;

        var benchmarkList = [];
        $scope.dynamic_benchmark_summary = {
            name: ":summary:",
            full_name: ":summary:",
            label: 'Summary of selected benchmarks',
            padding: '',
            type: 'dynamic_benchmark_summary'
        };
        benchmarkList.push($scope.dynamic_benchmark_summary);
        benchmarkList.push({ name: "/", full_name: "/", label: 'Overall summary', padding: '', type: 'root_benchmark_group' });
        _.each(_.groupBy(response[1].data, 'group'), function(benchmarks, group) {
            benchmarkList.push({ name: group, full_name: group, label: group + ' (summary)', padding: '  ', type: 'benchmark_group' });
            _.each(benchmarks, function(benchmark) {
                benchmark.type = 'benchmark';
                benchmark.label = benchmark.name;
                benchmark.full_name = benchmark.group + benchmark.name;
                benchmark.full_label = benchmark.full_name;
                benchmark.padding = '    ';
                benchmarkList.push(benchmark);
            });
        });
        $scope.benchmarkList = benchmarkList;

        $scope.environmentList = response[2].data;

        function defaultStartDate() {
            var d = new Date();
            d.setDate(d.getDate() - 30);
            d.setHours(0);
            d.setMinutes(0);
            d.setSeconds(0);
            return d;
        }

        var defaults;
        if ($routeParams.branch || $routeParams.benchmark || $routeParams.environment) {
            defaults = {
                branch: $routeParams.branch,
                benchmarks: forceArray($routeParams.benchmark),
                environments: forceArray($routeParams.environment),
                startDate: $routeParams.startDate && new Date($routeParams.startDate * 1000),
                endDate: $routeParams.endDate && new Date($routeParams.endDate * 1000),
                limit: $routeParams.limit
            };
        } else {
            defaults = {
                limit: '-100',
                startDate: defaultStartDate(),
                branch: 'master',
                benchmarks: [':summary:'],
                environments: _.map($scope.environmentList, function(env) {
                    return env.identifier;
                })
            };
        }

        if (defaults.branch) {
            $scope.branch = _.find($scope.branchList, ['branch_name', defaults.branch]);
            if (! $scope.branch) {
                $scope.branch = $scope.branchList[0];
            }
        }
        $scope.environments = _.map($scope.environmentList, function(env) {
            env.selected = defaults.environments.indexOf(env.identifier) > -1;
            return env;
        });
        $scope.benchmarks = _.map(defaults.benchmarks, function(b) {
            return _.find($scope.benchmarkList, ['full_name', b])
        });

        $scope.limit = defaults.limit;
        $scope.startDate = defaults.startDate;
        $scope.endDate = defaults.endDate;

    }).then($scope.change);

}]);
