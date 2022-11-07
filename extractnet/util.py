"""
The Levenshtein distance code was originally taken from (retrieved June 21, 2012):
   http://mwh.geek.nz/2009/04/26/python-damerau-levenshtein-distance/

It may eventually be updated to use different scores for insertions, deletions,
transpositions, etc. For the time being, however, it remains as presented in
the article.
"""
from __future__ import division
import os
from sklearn.pipeline import FeatureUnion, make_union
import ftfy
import dateparser
import regex # use by dateparser

from .compat import range_, string_
from .features import get_feature
from .sequence_tagger.models import NON_WORD_CHAR
# for sanity check function
from .metadata_extraction.url_utils import validate_date

get_module_res = lambda *res: os.path.normpath(os.path.join(
    os.getcwd(), os.path.dirname(__file__), *res))

def dameraulevenshtein(seq1, seq2):
    """Calculate the Damerau-Levenshtein distance between sequences.

    This distance is the number of additions, deletions, substitutions,
    and transpositions needed to transform the first sequence into the
    second. Although generally used with strings, any sequences of
    comparable objects will work.

    Transpositions are exchanges of *consecutive* characters; all other
    operations are self-explanatory.

    This implementation is O(N*M) time and O(M) space, for N and M the
    lengths of the two sequences.

    >>> dameraulevenshtein('ba', 'abc')
    2
    >>> dameraulevenshtein('fee', 'deed')
    2

    It works with arbitrary sequences too:
    >>> dameraulevenshtein('abcd', ['b', 'a', 'c', 'd', 'e'])
    2
    """
    # codesnippet:D0DE4716-B6E6-4161-9219-2903BF8F547F
    # Conceptually, this is based on a len(seq1) + 1 * len(seq2) + 1 matrix.
    # However, only the current and two previous rows are needed at once,
    # so we only store those.
    oneago = None
    thisrow = list(range_(1, len(seq2) + 1)) + [0]
    for x in range_(len(seq1)):
        # Python lists wrap around for negative indices, so put the
        # leftmost column at the *end* of the list. This matches with
        # the zero-indexed strings and saves extra calculation.
        twoago, oneago, thisrow = oneago, thisrow, [0] * len(seq2) + [x + 1]
        for y in range_(len(seq2)):
            delcost = oneago[y] + 1
            addcost = thisrow[y - 1] + 1
            subcost = oneago[y - 1] + (seq1[x] != seq2[y])
            thisrow[y] = min(delcost, addcost, subcost)
            # This block deals with transpositions
            if (x > 0 and y > 0 and seq1[x] == seq2[y - 1] and
                    seq1[x - 1] == seq2[y] and seq1[x] != seq2[y]):
                thisrow[y] = min(thisrow[y], twoago[y - 2] + 1)
    return thisrow[len(seq2) - 1]


def evaluation_metrics(predicted, actual, bow=True):
    """
    Input:
        predicted, actual = lists of the predicted and actual tokens
        bow: if true use bag of words assumption
    Returns:
        precision, recall, F1, Levenshtein distance
    """
    if bow:
        p = set(predicted)
        a = set(actual)

        true_positive = 0
        for token in p:
            if token in a:
                true_positive += 1
    else:
        # shove actual into a hash, count up the unique occurances of each token
        # iterate through predicted, check which occur in actual
        from collections import defaultdict
        act = defaultdict(lambda: 0)
        for token in actual:
            act[token] += 1

        true_positive = 0
        for token in predicted:
            if act[token] > 0:
                true_positive += 1
                act[token] -= 1

        # for shared logic below
        p = predicted
        a = actual

    try:
        precision = true_positive / len(p)
    except ZeroDivisionError:
        precision = 0.0
    try:
        recall = true_positive / len(a)
    except ZeroDivisionError:
        recall = 0.0
    try:
        f1 = 2.0 * (precision * recall) / (precision + recall)
    except ZeroDivisionError:
        f1 = 0.0

    # return (precision, recall, f1, dameraulevenshtein(predicted, actual))
    return (precision, recall, f1)


def get_and_union_features(features):
    """
    Get and combine features in a :class:`FeatureUnion`.

    Args:
        features (str or List[str], ``Features`` or List[``Features``], or List[Tuple[str, ``Features``]]):
            One or more features to be used to transform blocks into a matrix of
            numeric values. If more than one, a :class:`FeatureUnion` is
            automatically constructed. Example inputs::

                features = 'weninger'
                features = ['weninger', 'kohlschuetter']
                features = WeningerFeatures()
                features = [WeningerFeatures(), KohlschuetterFeatures()]
                features = [('weninger', WeningerFeatures()), ('kohlschuetter', KohlschuetterFeatures())]

    Returns:
        :class:`FeatureUnion` or ``Features``
    """
    if not features:
        raise ValueError('invalid `features`: may not be null')
    if isinstance(features, (list, tuple)):
        if isinstance(features[0], tuple):
            return FeatureUnion(features)
        elif isinstance(features[0], string_):
            return FeatureUnion([(feature, get_feature(feature)) for feature in features])
        else:
            return make_union(*features)
    elif isinstance(features, string_):
        return get_feature(features)
    else:
        return features


def convert_segmentation_to_text(pred_label, text):
    names = []
    name = ''

    for idx, char in enumerate(text):
        if pred_label[idx] == 'B':
            if len(name) > 0:
                names.append(NON_WORD_CHAR.sub('',name).strip())
                name = ''
            name += char
        elif pred_label[idx] == 'I':
            name += char
        else: # O
            if len(name) > 0:
                names.append(NON_WORD_CHAR.sub('',name).strip())
                name = ''
    if len(name) > 0 and NON_WORD_CHAR.sub('', name):
        names.append(NON_WORD_CHAR.sub('', name).strip())

    return names

def fix_encoding(text):
    if isinstance(text, str):
        text = ftfy.fix_text(ftfy.fix_encoding(text))
        if '\\u' in text:
            try:
                text = text.encode().decode('unicode_escape')
            except UnicodeDecodeError as e:
                return text
        return text
    elif isinstance(text, list):
        return [ ftfy.fix_text(ftfy.fix_encoding(t)) for t in text ]


def merge_results(r1, r2):

    for key in r2.keys():
        if key not in r1:
            r1[key] = r2[key]
        elif isinstance(r1[key], str) and isinstance(r2[key], str):
            r1[key] = [r1[key], r2[key]]
        elif isinstance(r1[key], str) and isinstance(r2[key], list):
            r1[key] = r2[key] + [r1[key]]
        elif isinstance(r1[key], list) and isinstance(r2[key], str):
            r1[key] = r1[key] + [r2[key]]
        elif isinstance(r1[key], list) and isinstance(r2[key], list):
            r1[key] += r2[key]
    return r1

def remove_empty_keys(r1):
    if r1 is None:
        return {}
    for key in list(r1.keys()):
        if r1[key] is None:
            r1.pop(key)
    return r1


def priority_merge(x, main):
    # merge x outputs into `main` results
    z = x.copy()
    z.update(main)
    return z

def attribute_sanity_check(content, **kwargs):
    if 'date' in content and isinstance(content['date'], str):
        date = content['date']
        try:
            content['date'] = dateparser.parse(date)
        except regex._regex_core.error:
            pass

    if 'url' in kwargs and 'date' in content:
        url = kwargs['url']
        content['date'] = validate_date(url, content['date'])

    if 'author' in content and isinstance(content['author'], list):
        author_str = ','.join(content['author'])
        content['author'] = author_str

    return content