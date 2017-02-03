import os

from django.conf import settings
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile

from django.core.management.base import BaseCommand, CommandError
from kl.search.models import Word


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--limit', default=100000)
        parser.add_argument('--offset', default=0)

    def handle(self, *args, **options):
        offset = int(options['offset'])
        limit = int(options['limit'])
        # limit = 10000
        from django.db import connections
        cursor = connections['legacy'].cursor()
        cursor.execute('''
        select
        id,
        word,
        length,
        part_of_speech,
        language,
        name,
        definition,
        first1,
        first2,
        last1,
        last2
        from words
        limit %(limit)s
        offset %(offset)s
        ''', {
            'offset': offset,
            'limit': limit,
        })
        i = 0
        for row in cursor.fetchall():
            (
                id,
                word,
                length,
                part_of_speech,
                language,
                name,
                definition,
                first1,
                first2,
                last1,
                last2,
            ) = row
            # oid, title, description, is_published, create_date, image = row
            if Word.objects.filter(id=id).exists():
                continue
            word = Word(
                id=id,
                word=word,
                length=length,
                name=name,
                part_of_speech=part_of_speech,
                language=language,
                first1=first1,
                first2=first2,
                last1=last1,
                last2=last2,
            )
            word.save()
            i += 1
            print(str(i).ljust(5), repr(word))

        print("NEXT OFFSET", offset + limit)
