from django.conf.urls import url

from kl.search import views


urlpatterns = [
    url(
        r'^$',
        views.home,
        name='home'
    ),
    url(
        r'^json/$',
        views.home,
        {'json': True},
        name='home',
    ),
    url(
        r'^searches/(?P<year>\d{4})/(?P<month>\w+)/$',
        views.searches_summary,
        name='searches_summary'
    ),
    url(
        r'^about/crosstips/$',
        views.about_crosstips,
        name='about_crosstips'
    ),

]
