from django.db import models


class Word(models.Model):
    """
    A Word has two important parts: the word, its length
    and there's also the optional part_of_speech. The length always
    has to be that of the word:

        >>> w = Word.objects.create(word=u'Peter',
        ...                         part_of_speech=u'egenamn',
        ...                         language='sv')
        >>> w.length == len(u'Peter')
        True

    """
    class Meta:
        db_table = 'words'

    word = models.CharField(max_length=40)
    language = models.CharField(max_length=5)
    length = models.IntegerField()
    part_of_speech = models.CharField(max_length=20, null=True)
    definition = models.CharField(max_length=250, null=True)
    name = models.BooleanField()
    # used for optimization
    first1 = models.CharField(max_length=1)
    first2 = models.CharField(max_length=2)
    last1 = models.CharField(max_length=1)
    last2 = models.CharField(max_length=2)

    def __str__(self):
        return self.word

    def __repr__(self):
        return '<{} {!r} ({})>'.format(
            self.__class__.__name__,
            self.word,
            self.language
        )

    def __init__(self, *args, **kwargs):
        if 'word' in kwargs:
            if 'length' in kwargs:
                assert kwargs['length'] == len(kwargs['word'])
            else:
                kwargs['length'] = len(kwargs['word'])

            if 'first1' in kwargs:
                try:
                    assert kwargs['first1'] == kwargs['word'][0].lower()
                except AssertionError:
                    kwargs['first1'] = kwargs['word'][0].lower()
                    # print((kwargs['first1'], kwargs['word']))
                    # raise
            else:
                kwargs['first1'] = kwargs['word'][0].lower()
            if 'first2' in kwargs:
                try:
                    assert kwargs['first2'] == kwargs['word'][:2].lower()
                except AssertionError:
                    kwargs['first2'] = kwargs['word'][:2].lower()
                    # print((kwargs['first2'], kwargs['word']))
                    # raise
            else:
                kwargs['first2'] = kwargs['word'][:2].lower()

            if 'last1' in kwargs:
                assert kwargs['last1'] == kwargs['word'][-1].lower()
            else:
                kwargs['last1'] = kwargs['word'][-1].lower()
            if 'last2' in kwargs:
                assert kwargs['last2'] == kwargs['word'][-2:].lower()
            else:
                kwargs['last2'] = kwargs['word'][-2:].lower()

        super(Word, self).__init__(*args, **kwargs)


class Search(models.Model):
    """ A search is a record of someone doing a search.
    """

    class Meta:
        db_table = 'searches'
        verbose_name_plural = 'Searches'

    search_word = models.CharField(max_length=40)
    add_date = models.DateTimeField('date added', auto_now_add=True,
                                    db_index=True)
    user_agent =  models.CharField(max_length=200, default='')
    ip_address =  models.CharField(max_length=15, default='')
    language = models.CharField(max_length=5, default='')
    search_type = models.CharField(max_length=50, default='')

    found_word = models.ForeignKey(Word, null=True, blank=True,
        on_delete=models.deletion.CASCADE)

    def __str__(self):
        return self.search_word
