from django.conf import settings
from django.conf.urls import url, include
from django.conf.urls.static import static



urlpatterns = [
    url(
        '',
        include('kl.search.urls', namespace='search')
    ),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.STATIC_ROOT
    )
