from django.conf import settings
from django.utils.translation import get_language
from django.utils import timezone
from django.core.urlresolvers import reverse

from kl.search.views import get_search_stats


def context(request):
    data = {
        'DEBUG': settings.DEBUG,
        'base_template': 'search/base.html',
        'mobile_version': False,
        'mobile_user_agent': False,
        'GOOGLE_ANALYTICS': settings.GOOGLE_ANALYTICS,
    }

    language = get_language()
    data.update(get_search_stats(language))

    today = timezone.now()
    data['searches_summary_link'] = reverse(
        'search:searches_summary',
        args=(
            today.strftime('%Y'),
            today.strftime('%B')
        )
    )

    return data
