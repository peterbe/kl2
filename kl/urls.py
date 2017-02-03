from django.conf import settings
from django.conf.urls import url, include
from django.conf.urls.static import static

import kl.search.urls


urlpatterns = [
    url(
        '',
        include(kl.search.urls.urlpatterns, namespace='search')
    ),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.STATIC_ROOT
    )
