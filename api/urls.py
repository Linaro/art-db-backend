from django.conf.urls import include, url

from rest_framework import routers

from . import views

router = routers.DefaultRouter()
router.register(r'token', views.TokenViewSet)
router.register(r'manifest', views.ManifestViewSet)
router.register(r'result', views.ResultViewSet)
router.register(r'resultdata', views.ResultDataViewSet)
router.register(r'benchmark', views.BenchmarkViewSet)
router.register(r'test', views.TestJobViewSet)

# functional view
router.register(r'compare', views.CompareResults, base_name="compare")

urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'details/', views.ResultDataForManifest.as_view()),
]

