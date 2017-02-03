import datetime
import re
from random import shuffle
from collections import defaultdict

from django.utils.translation import (
    activate,
    get_language_info,
    get_language,
)
from django import http
from django.shortcuts import render
from django.core.cache import cache
from django.conf import settings
from django.utils.translation import get_language
from django.utils.translation import ugettext as _
from django.utils import timezone

try:
    from nltk.corpus import wordnet
except ImportError:
    wordnet = None


from kl.search.models import Word, Search

SEARCH_SUMMARY_SKIPS = (
    'crossword', 'korsord', 'fuck', 'peter', 'motherfucker',
)

def niceboolean(value):
    if isinstance(value, bool):
        return value
    falseness = ('', 'no', 'off', 'false', 'none', '0', 'f')
    return str(value).lower().strip() not in falseness


def uniqify(seq, idfun=None): # Alex Martelli ******* order preserving
    if idfun is None:
        def idfun(x): return x
    seen = set()
    result = []
    for item in seq:
        marker = idfun(item)
        # in old Python versions:
        # if seen.has_key(marker)
        # but in new ones:
        ##if marker in seen: continue
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result

class SearchResult(object):
    def __init__(self, word, definition='', by_clue=None):
        self.word = word
        self.definition = definition
        self.by_clue = by_clue



def home(request, json=False, record_search=True):
    # By default we are set to record the search in our stats
    # This can be overwritten by a CGI variable called 'r'
    # E.g. r=0 or r=no
    if request.GET.get('r'):
        record_search = niceboolean(request.GET.get('r'))

    language = request.GET.get('lang', get_language()).lower()

    slots = None

    if request.GET.get('l'):
        try:
            length = int(request.GET.get('l'))
        except ValueError:
            return http.HttpResponseRedirect('/?error=length')
        slots = request.GET.getlist('s')
        # if not type(slots) is list:
        if not isinstance(slots, list):
            return http.HttpResponseRedirect('/?error=slots')

        notletters = request.GET.get('notletters', '').upper()
        notletters = [x.strip() for x in notletters.split(',')
                      if len(x.strip()) == 1 and not x.strip().isdigit()]

        if not len(slots) >= length:
            return http.HttpResponseRedirect('/?error=slots&error=length')

        if not [x for x in slots if x.strip()]:
            # all blank
            return http.HttpResponseRedirect('/?error=slots')

        clues = request.GET.get('clues', '')
        if clues and ' ' in clues and ',' not in clues:
            clues = clues.replace(' ',', ')
        clues = [
            x.strip() for x in clues.split(',')
            if (
                x.strip() and
                x.strip().lower() not in STOPWORDS and
                not x.count(' ')
            )
        ]

        search_results = [] # the final simple list that is sent back

        for clue in clues:
            alternatives = _find_alternative_synonyms(
                clue,
                slots[:length],
                language,
                notletters=notletters,
                request=request
            )
            search_results.extend([
                SearchResult(x, by_clue=clue)
                for x in alternatives
            ])

        # find some alternatives
        search = ''.join([x and x.lower() or ' ' for x in slots[:length]])
        cache_key = '_find_alternatives_%s_%s' % (search, language)
        if notletters:
            cache_key += '__not' + ''.join(notletters)
        cache_key = cache_key.replace(' ','_')
        if re.findall('\s', cache_key):
            raise ValueError(
                'invalid cache_key search=%r, language=%r' % (search, language)
            )

        alternatives = cache.get(cache_key)
        if alternatives is None:
            alternatives = _find_alternatives(
                slots[:length],
                language,
                notletters=notletters
            )
            cache.set(cache_key, alternatives, 60 * 60 * 24)

        alternatives_count = len(alternatives)
        alternatives_truncated = False
        if alternatives_count > 100:
            alternatives = alternatives[:100]
            alternatives_truncated = True

        result = dict(
            length=length,
            search=search,
            word_count=alternatives_count,
            alternatives_truncated=alternatives_truncated,
        )
        already_found = [x.word for x in search_results]
        search_results.extend([
            SearchResult(each.word, definition=each.definition)
            for each in alternatives
            if each.word not in already_found
        ])

        match_points = None
        match_points = []
        if search_results:
            first_word = search_results[0].word
            for i, letter in enumerate(first_word):
                if letter.lower() == search[i]:
                    match_points.append(1)
                else:
                    match_points.append(0)
            result['match_points'] = match_points

        result['words'] = []
        for search_result in search_results:
            v = dict(word=search_result.word)
            if search_result.definition:
                v['definition'] = search_result.definition
            if search_result.by_clue:
                v['by_clue'] = search_result.by_clue
            result['words'].append(v)

        if alternatives_count == 1:
            result['match_text'] = _("1 match found")
        elif alternatives_count:
            if alternatives_truncated:
                result['match_text'] = _(
                    "%(count)s matches found but only showing first 100"
                ) % dict(count=alternatives_count)
            else:
                result['match_text'] = _("%(count)s matches found") % dict(
                    count=alternatives_count
                )
        else:
            result['match_text'] = _("No matches found unfortunately :(")

        found_word = None
        if len(search_results) == 1:
            try:
                found_word = Word.objects.get(
                    word=search_results[0].word,
                    language=language
                )
            except Word.DoesNotExist:
                # this it was probably not from the database but
                # from the wordnet stuff
                found_word = None

        if record_search:

            _record_search(
                search,
                user_agent=request.META.get('HTTP_USER_AGENT',''),
                ip_address=request.META.get('REMOTE_ADDR',''),
                found_word=found_word,
                language=language
            )

        request.session['has_searched'] = True

        if json:
            return http.JsonResponse(result)
            # return _render_json(result)

    else:
        length = ''

    show_example_search = not bool(request.session.get('has_searched'))
    most_recent_search_word = None
    if not show_example_search:
        most_recent_search_word = _get_recent_search_word(request)

    lang = get_language()
    accept_clues = (
        wordnet is not None and lang.lower() in ('en', 'en-gb', 'en-us')
    )

    context = {
        'length': length,
        'slots': slots,
        'accept_clues': accept_clues,
        'show_example_search': show_example_search,
        'most_recent_search_word': most_recent_search_word,
    }
    return render(request, 'search/home.html', context)


def _find_alternatives(slots, language, notletters=[]):
    length = len(slots)

    if length == 1:
        return Word.objects.filter(length=1, word=slots[0], language=language)

    filter_ = dict(length=length, language=language)
    slots = [x and x.lower() or ' ' for x in slots]
    search = ''.join(slots)
    start = ''
    end = ''
    try:
        start = re.findall('^\w+', search)[0]
        if len(start) > 1:
            filter_['first2'] = start[:2].lower()
            if len(start) > 2:
                filter_['word__istartswith'] = start
        else:
            filter_['first1'] = start.lower()
    except IndexError:
        pass

    try:
        end = re.findall('\w+$', search)[0]
        if len(end) > 1:
            filter_['last2'] = end[-2:].lower()
            if len(end) > 2:
                filter_['word__iendswith'] = end
        else:
            filter_['last1'] = end.lower()

    except IndexError:
        pass

    def filter_match(match):
        if end:
            matchable_string = search[len(start):-len(end)]
            found_string = match.word[len(start):-len(end)]
        else:
            matchable_string = search[len(start):]
            found_string = match.word[len(start):]

        assert len(matchable_string) == len(found_string), \
        "matchable_string=%r, found_string=%r" % (matchable_string, found_string)

        for i, each in enumerate(matchable_string):
            if each != ' ' and each != found_string[i]:
                # can't be match
                return False
        return True

    search_base = Word.objects
    limit = 10000
    # if the filter is really vague and the length is high we're going to get
    # too many objects and we need to cut our losses.
    if filter_['length'] > 5:
        if filter_.get('word__istartswith') and filter_.get('word__iendswith'):
            # It's long but has a startswith and an endswith, increase the limit
            limit = 5000
        elif filter_.get('word__istartswith') or filter_.get('word__iendswith'):
            # we're going to get less than above but still many
            limit = 2500
        else:
            limit = 1000

    # if there's neither a start or a end (e.g. '_E_E_A_') it will get all words
    # that are of that length then end truncate the result set then filter them
    # as a string operation. Then there's a chance it might not ever test word we
    # are looking for.
    if not start and not end:
        # must come up with some other crazy icontains filter
        # Look for the longest lump of letter. For example in '_E_ERA_' 'era' is
        # the longest lump
        #lumps = re.findall('\w+', search)
        lumps = search.split()

        longest = sorted(lumps, lambda x,y: cmp(len(y), len(x)))[0]
        if len(longest) > 1:
            filter_['word__icontains'] = longest
        else:
            for each in uniqify(lumps):
                search_base = search_base.filter(word__icontains=each)

            limit = search_base.filter(**filter_).order_by('word').count()
    elif (start and len(start) <= 2) or (end and len(end) <= 2):
        # If you search for somethin like "___TAM__T"
        # We so far only know it's 9 characters long (french as 21k 9 characters long
        # words).
        # We also have one tiny little 't' at the end but there's still
        # 4086 options
        for lump in re.findall(r'\s(\w+)\s', search):
            filter_['word__icontains'] = lump

    search_qs = search_base.filter(**filter_)
    for notletter in notletters:
        search_qs = search_qs.exclude(word__icontains=notletter)

    all_matches = [x for x
                   in search_qs.order_by('word')[:limit]
                   if filter_match(x)]
    return uniqify(all_matches, lambda x: x.word.lower())



def _find_alternative_synonyms(
    word,
    slots,
    language,
    notletters=None,
    request=None
):
    length = len(slots)
    if notletters is None:
        notletters = []

    slots = [x and x.lower() or ' ' for x in slots]
    search = ''.join(slots)
    start = ''
    end = ''
    try:
        start = re.findall('^\w+', search)[0]
    except IndexError:
        pass

    try:
        end = re.findall('\w+$', search)[0]
    except IndexError:
        pass

    def filter_match(word):

        if end and not word.endswith(end):
            # Don't even bother
            return False
        elif start and not word.startswith(start):
            # Don't even bother
            return False

        if end:
            matchable_string = search[len(start):-len(end)]
            found_string = word[len(start):-len(end)]
        else:
            matchable_string = search[len(start):]
            found_string = word[len(start):]
        assert len(matchable_string) == len(found_string)
        for i, each in enumerate(matchable_string):
            if each != ' ' and each != found_string[i]:
                # can't be match
                return False
        return True

    def test(word):
        if len(word) == length:
            if not notletters:
                for letter in word:
                    if letter.upper() in notletters:
                        return False
            return filter_match(word)

    for variation in _get_variations(word, greedy=True, request=request):
        if test(variation):
            yield variation


def _get_variations(word, greedy=False,
                    store_definitions=True,
                    request=None):
    a = _get_variations_wordnet(
        word,
        greedy=greedy,
        store_definitions=store_definitions
    )
    return a
    # b = _get_variations_synonym_dot_com(
    #     word,
    #     greedy=greedy,
    #     store_definitions=store_definitions,
    #     request=request
    # )
    # return a + b


def _record_search(
    search_word,
    user_agent='',
    ip_address='',
    found_word=None,
    language=None,
    search_type='',
):
    if len(user_agent) > 200:
        user_agent = user_agent[:200]
    if len(ip_address) > 15:
        import warnings
        warnings.warn("ip_address too long (%r)" % ip_address)
        ip_address = ''
    elif ip_address == '127.0.0.1' and settings.DEBUG:
        # because 127.0.0.1 can't be looked up, use a random other one
        examples = '125.239.15.42,114.199.97.224,68.190.165.25,208.75.100.212,'\
                   '61.29.84.154,72.49.16.234,66.57.228.64,196.25.255.250,'\
                   '141.117.6.97,85.68.18.183,90.157.186.202'.split(',')
        shuffle(examples)
        ip_address = examples[0]

    Search.objects.create(
        search_word=search_word,
        user_agent=user_agent.strip(),
        ip_address=ip_address.strip(),
        found_word=found_word,
        language=language,
        search_type=search_type,
    )


def _get_recent_search_word(request):
    # _today = datetime.datetime.today()
    _today = timezone.now()
    _since = datetime.datetime(_today.year, _today.month, 1)

    _extra_exclude = dict(found_word__word__in=list(SEARCH_SUMMARY_SKIPS))
    if request.META.get('HTTP_USER_AGENT'):
        _extra_exclude['user_agent'] = request.META.get('HTTP_USER_AGENT')
    if request.META.get('REMOTE_ADDR'):
        _extra_exclude['ip_address'] = request.META.get('REMOTE_ADDR')

    _extra_filter = dict()
    # Special hack! Since the search summary has a cache of 1 hour,
    # don't include things that are too recent
    _extra_filter['add_date__lt'] = _today - datetime.timedelta(hours=1)

    return _find_recent_search_word(
        get_language(),
        since=_since,
        random=True,
        extra_exclude=_extra_exclude,
        **_extra_filter,
    )


def _find_recent_search_word(
    language,
    since=None,
    random=False,
    extra_exclude={},
    **extra_filter
):
    searches = Search.objects.filter(
        language=language,
        found_word__isnull=False,
        **extra_filter
    ).select_related('found_word')

    if since:
        searches = searches.filter(add_date__gte=since)
    searches = searches.exclude(**extra_exclude)

    if random:
        # For some bizzare reason it seems that even if the exclude above
        # has found_word__word__in=SEARCH_SUMMARY_SKIPS it still returns
        # words from that list!!!!
        # Hence this list comprehension.
        found_words = [x.found_word for x in searches
                       if x.found_word.word not in SEARCH_SUMMARY_SKIPS]
        shuffle(found_words)
        try:
            return found_words[0]
        except IndexError:
            return None
    else:
        searches = searches.order_by('-add_date')
        return searches[0].found_word
    return None


def get_search_stats(language):
    # Total no words in our database
    cache_key = 'no_total_words_%s' % language
    no_total_words = cache.get(cache_key)
    if no_total_words is None:
        no_total_words = Word.objects.filter(language=language).count()
        cache.set(cache_key, no_total_words, 60 * 60 * 24 * 30)

    today = timezone.now()

    # Searches today
    # today_midnight = datetime.datetime(
    #     today.year,
    #     today.month,
    #     today.day, 0, 0, 0)
    today_midnight = today - datetime.timedelta(days=1)
    cache_key = 'no_searches_today_%s' % language
    no_searches_today = cache.get(cache_key)
    if no_searches_today is None:
        no_searches_today = Search.objects.filter(
            language=language,
            add_date__gte=today_midnight
        ).count()
        cache.set(cache_key, no_searches_today, 60 * 60)

    # Searches yesterday
    cache_key = 'no_searches_yesterday_%s' % language
    no_searches_yesterday = cache.get(cache_key)
    if no_searches_yesterday is None:
        yesterday_midnight = today_midnight - datetime.timedelta(days=1)
        no_searches_yesterday = Search.objects.filter(language=language,
            add_date__range=(yesterday_midnight, today_midnight)
        ).count()
        cache.set(cache_key, no_searches_yesterday, 60 * 60 * 24)

    # Searches this week
    cache_key = 'no_searches_this_week_%s' % language
    no_searches_this_week = cache.get(cache_key)
    if no_searches_this_week is None:
        # find the first monday
        monday_midnight = today_midnight
        while monday_midnight.strftime('%A') != 'Monday':
            monday_midnight = monday_midnight - datetime.timedelta(days=1)

        no_searches_this_week = Search.objects.filter(
            language=language,
            add_date__gt=monday_midnight
        ).count()
        cache.set(cache_key, no_searches_this_week, 60 * 60 * 24)

    # Searches this month
    cache_key = 'no_searches_this_month_%s' % language
    no_searches_this_month = cache.get(cache_key)
    if no_searches_this_month is None:
        first_day_month = today.replace(day=1)
        no_searches_this_month = Search.objects.filter(
            language=language,
            add_date__gte=first_day_month
        ).count()
        cache.set(cache_key, no_searches_this_month, 60 * 60)

    # Searches this year
    cache_key = 'no_searches_this_year_%s' % language
    no_searches_this_year = cache.get(cache_key)
    if no_searches_this_year is None:
        # first_day_year = datetime.datetime(today.year, 1, 1, 0, 0, 0)
        first_day_year = today.replace(month=1, day=1)
        no_searches_this_year = Search.objects.filter(
            language=language,
            add_date__gte=first_day_year
        ).count()
        cache.set(cache_key, no_searches_this_year, 60 * 60)

    return {
        'no_total_words': no_total_words,
        'no_searches_today': no_searches_today,
        'no_searches_yesterday': no_searches_yesterday,
        'no_searches_this_week': no_searches_this_week,
        'no_searches_this_month': no_searches_this_month,
        'no_searches_this_year': no_searches_this_year,
    }


MONTH_NAMES = []
for i in range(1, 13):
    d = datetime.date(2009, i, 1)
    MONTH_NAMES.append(d.strftime('%B'))


def searches_summary(request, year, month, atleast_count=2,
                     lookup_definitions=False):

    first_search_date = Search.objects.all().order_by('add_date')[0].add_date
    last_search_date = Search.objects.all().order_by('-add_date')[0].add_date

    year = int(year)
    try:
        month_nr = [x.lower() for x in MONTH_NAMES].index(month.lower()) + 1
    except ValueError:
        raise http.Http404("Unrecognized month name")
    # turn that into a date
    since = datetime.date(year, month_nr, 1)

    if (month_nr + 1) > 12:
        since_month_later = datetime.date(year+1, 1, 1)
    else:
        since_month_later = datetime.date(year, month_nr+1, 1)

    today = timezone.now()
    since_month_later_datetime = today.replace(
        year=since_month_later.year,
        month=since_month_later.month,
        day=since_month_later.day
    )

    next_month_link = None

    if since_month_later_datetime < first_search_date:
        raise http.Http404("Too far back in time")
    if since_month_later_datetime < last_search_date:
        next_month_link = since_month_later.strftime("/searches/%Y/%B/")

    since_datetime = today.replace(
        year=since.year,
        month=since.month,
        day=since.day
    )

    previous_month_link = None

    if since_datetime > last_search_date:
        raise http.Http404("Too far into the future")

    elif since_datetime > first_search_date:
        if (month_nr - 1) < 1:
            since_month_earlier = datetime.date(year-1, 12, 1)
        else:
            since_month_earlier = datetime.date(year, month_nr-1, 1)

        previous_month_link = since_month_earlier.strftime("/searches/%Y/%B/")

    base_searches = Search.objects.filter(
        add_date__gte=since,
        add_date__lt=since_month_later
    )

    found_searches = base_searches.exclude(
        found_word=None
    ).select_related(
        'found_word'
    ).exclude(
        found_word__word__in=list(SEARCH_SUMMARY_SKIPS)
    )

    found_words = defaultdict(list)
    definitions = {}
    for each in found_searches:
        found_words[each.language].append(each.found_word.word)

        if each.language not in definitions:
            definitions[each.found_word.language] = {}
        if each.found_word.definition:
            definitions[each.found_word.language][each.found_word.word.lower()]\
              = each.found_word.definition.splitlines()


    found_words = dict(found_words)

    found_words_repeats = {}
    for language, words in found_words.items():
        counts = defaultdict(int)
        for word in words:
            if len(word) < 2:
                # don't want to find single character words
                # It's a bug that they're even in there
                continue
            counts[word.lower()] += 1
            found_words_repeats[language] = sorted(
                [k for (k, v) in counts.items()
                if v >= atleast_count],
                key=lambda x: x[1]
            )

    if lookup_definitions:
        for lang, words in found_words_repeats.items():
            for word in words:
                try:
                    definitions[lang][word]
                except KeyError:
                    if lang in ('en-us','en-gb'):
                        # wordnet
                        definition = _get_word_definition(word, language=lang)
                    else:
                        definition = None

                    if not definition:
                        definition = _get_word_definition_scrape(word, language=lang)
                    if definition:
                        add_word_definition(word, definition, language=lang)

    # bake the definitions into found_words_repeats
    for lang, words in found_words_repeats.items():
        for i, word in enumerate(words):
            words_dict = dict(word=word)
            if lang in definitions:
                if word in definitions[lang]:
                    words_dict = dict(words_dict, definitions=definitions[lang][word])
            found_words_repeats[lang][i] = words_dict

    all_words_plain = set()
    for records in found_words_repeats.values():
        for record in records:
            all_words_plain.add(record['word'].lower())
    all_words_plain = list(all_words_plain)

    context = {
        # 'language': language,
        'month': month,
        'year': year,
        'all_words_plain': all_words_plain,
        'found_words_repeats': found_words_repeats,
        'previous_month_link': previous_month_link,
        'next_month_link': next_month_link,
    }
    return render(request, 'search/searches_summary.html', context)


def about_crosstips(request):
    return render(request, 'search/about-crosstips.html')
