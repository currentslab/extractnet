# pylint:disable-msg=E0611,I1101
"""
Module bundling functions related to HTML and text processing.
"""
## This file is available from https://github.com/adbar/trafilatura
## under GNU GPL v3 license

# import csv
import logging
from html import unescape
from lxml import etree, html
from functools import lru_cache
import urllib
import urllib.parse
import json
import urllib.request
# use faster detection module
try:
    from cchardet import detect as cchardet_detect
except ImportError:
    cchardet_detect = None
from charset_normalizer import from_bytes
from bs4 import BeautifulSoup as bs
from .constant import (
    HTML_PARSER, RECOVERY_PARSER, SPLIT_TOKENS, NO_TAG_SPACE, SPACE_TRIMMING,
    UNICODE_ALIASES, LINES_TRIMMING, CLEAN_META_TAGS,
    AUTHOR_EMAIL, AUTHOR_EMOJI_REMOVE, AUTHOR_PREFIX, AUTHOR_SPLIT,
    AUTHOR_REMOVE_SPECIAL, AUTHOR_REPLACE_JOIN, AUTHOR_REMOVE_NICKNAME, 
    AUTHOR_REMOVE_NUMBERS, AUTHOR_REMOVE_PREPOSITION, AUTHOR_TWITTER
)

LOGGER = logging.getLogger(__name__)


def re_xpath(self, path):
    return self.xpath(path, namespaces={
        're': 'http://exslt.org/regular-expressions'})
html.HtmlElement.re_xpath = re_xpath

def isutf8(data):
    """Simple heuristic to determine if a bytestring uses standard unicode encoding"""
    try:
        data.decode('UTF-8')
    except UnicodeDecodeError:
        return False
    else:
        return True

@lru_cache(maxsize=1114111)  # sys.maxunicode = 1114111
def return_printables_and_spaces(char):
    'Return a character if it belongs to certain classes'
    if char.isprintable() or char.isspace():
        return char
    return ''


def remove_control_characters(string):
    '''Prevent non-printable and XML invalid character errors'''
    return ''.join(map(return_printables_and_spaces, string))

@lru_cache(maxsize=1024)
def line_processing(line):
    '''Remove HTML space entities, then discard incompatible unicode
       and invalid XML characters on line level'''
    # spacing HTML entities: https://www.w3.org/MarkUp/html-spec/html-spec_13.html
    line = line.replace('&#13;', '\r').replace('&#10;', '\n').replace('&nbsp;', '\u00A0')
    # remove newlines that are not related to punctuation or markup
    # remove non-printable chars and normalize space characters (including Unicode spaces)
    line = trim(remove_control_characters(LINES_TRIMMING.sub(r' ', line)))
    # prune empty lines
    if all(map(str.isspace, line)):
        line = None
    return line

def detect_encoding(bytesobject):
    """"Read all input or first chunk and return a list of encodings"""
    # alternatives: https://github.com/scrapy/w3lib/blob/master/w3lib/encoding.py
    # unicode-test
    if isutf8(bytesobject):
        return ['utf-8']
    guesses = []
    # additional module
    if cchardet_detect is not None:
        cchardet_guess = cchardet_detect(bytesobject)['encoding']
        if cchardet_guess is not None:
            guesses.append(cchardet_guess.lower())
    # try charset_normalizer on first part, fallback on full document
    detection_results = from_bytes(bytesobject[:15000]) or from_bytes(bytesobject)
    # return alternatives
    if len(detection_results) > 0:
        guesses.extend([r.encoding for r in detection_results])
    # it cannot be utf-8 (tested above)
    return [g for g in guesses if g not in UNICODE_ALIASES]

def check_authors(authors, author_blacklist):
    new_authors = [
        author
        for author in authors.split('; ')
        if author.lower() not in [a.lower() for a in author_blacklist]
    ]
    if new_authors:
        return '; '.join(new_authors).strip('; ')
    return None

def load_html(htmlobject, encoding='utf-8'):
    """Load object given as input and validate its type
    (accepted: LXML tree, bytestring and string)
    """
    # use tree directly
    if isinstance(htmlobject, (etree._ElementTree, html.HtmlElement)):
        return htmlobject
    tree = None
    check_flag = False
    # try to detect encoding and convert to string
    if isinstance(htmlobject, bytes):
        # test
        if 'html' not in htmlobject[:50].decode(encoding=encoding, errors='ignore').lower():
            check_flag = True
        guessed_encoding = detect_encoding(htmlobject)
        if guessed_encoding is not None:
            if guessed_encoding == 'UTF-8':
                tree = html.fromstring(htmlobject, parser=HTML_PARSER)
            else:
                try:
                    htmlobject = htmlobject.decode(guessed_encoding)
                    tree = html.fromstring(htmlobject, parser=HTML_PARSER)
                except UnicodeDecodeError:
                    LOGGER.warning('encoding issue: %s', guessed_encoding)
                    tree = html.fromstring(htmlobject, parser=RECOVERY_PARSER)
        else:
            tree = html.fromstring(htmlobject, parser=RECOVERY_PARSER)
    # use string if applicable
    elif isinstance(htmlobject, str):
        # test
        if 'html' not in htmlobject[:50].lower():
            check_flag = True
        try:
            tree = html.fromstring(htmlobject, parser=HTML_PARSER)
        except ValueError:
            # try to parse a bytestring
            try:
                tree = html.fromstring(htmlobject.encode('utf8'), parser=HTML_PARSER)
            except Exception as err:
                LOGGER.error('parser bytestring %s', err)
        except Exception as err:
            LOGGER.error('parsing failed: %s', err)
    # default to None
    else:
        LOGGER.error('this type cannot be processed: %s', type(htmlobject))
    # further test: is it (well-formed) HTML at all?
    if tree is not None and check_flag is True:
        if len(tree) < 2:
            tree = None
    #if tree is None:
    #    if isinstance(htmlobject, bytes) or isinstance(htmlobject, str):
    #        # more robust parsing
    #        tree = fromsoup(htmlobject)
    return tree



def split_tags(string):
    if len(string) <= 1:
        return [string]
    match_token = SPLIT_TOKENS.search(string)
    try:
        if match_token is not None:
            split_token = match_token.group(0)
            return string.split(split_token)
    except TypeError:
        return [string]
    return [string]

@lru_cache(maxsize=128)
def trim(string):
    '''Remove unnecessary spaces within a text string'''
    try:
        # remove newlines that are not related to punctuation or markup + proper trimming
        return SPACE_TRIMMING.sub(r' ', NO_TAG_SPACE.sub(r' ', string)).strip(' \t\n\r\v')
    except TypeError:
        return None




def get_raw_html(url, cookie=None, headers_={}, params=None, lib='requests'):
	headers = {
		'Accept': "text/plain, */*; q=0.01",
		'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36',
		'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36',
		'cache-control': "no-cache",
		"sec-fetch-user": "?1",
		'sec-fetch-dest': 'document',
		'sec-fetch-site': 'same-origin',
		'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
	}
	if len(headers_) > 0:
		for key, value in headers_.items():
			headers[key] = value

	if type(cookie) == 'str':
		headers['cookie'] = cookie

	if params is not None:
		data = urllib.parse.urlencode(params)
		data = data.encode('ascii')
	else:
		data = None
	req = urllib.request.Request(url, data, headers)
	with urllib.request.urlopen(req) as response:
		raw_html = response.read()
		return raw_html.decode('UTF-8')

def parse_server_side_render(raw_html):
	if '<script type="application/ld+json">' in raw_html:
		return json.loads(raw_html.split('<script type="application/ld+json">', maxsplit=1)[1].split('</script>')[0].replace('//,',','),strict=False)
	return {}


def parse_ld_json(raw_html):
	results = []
	if '<script type="application/ld+json">' in raw_html:
		soup = bs(raw_html, 'lxml')
		for script_tag in soup.findAll('script', {'type': 'application/ld+json'}):
			json_string = script_tag.string
			if json_string and '@context' in json_string:
				payload = json.loads(json_string)
				if isinstance(payload, list):
					for load in payload:
						results.append(load)
				else:
					results.append(payload)
					if '@graph' in results[-1]:
						graph = results[-1]['@graph']
						if isinstance(graph, list):
							for load in graph:
								results.append(load)
						else:
							results.append(graph)

	return results


def normalize_authors(current_authors, author_string):
    '''Normalize author info to focus on author names only'''
    new_authors = []
    if author_string.lower().startswith('http') or AUTHOR_EMAIL.match(author_string):
        return current_authors
    if current_authors is not None:
        new_authors = current_authors.split('; ')
    # fix to code with unicode
    if '\\u' in author_string:
        author_string = author_string.encode().decode('unicode_escape')
    # fix html entities
    if '&#' in author_string or '&amp;' in author_string:
        author_string = unescape(author_string)
    # examine names
    for author in AUTHOR_SPLIT.split(author_string):
        author = trim(author)
        author = AUTHOR_EMOJI_REMOVE.sub('', author)
        # remove @username
        author = AUTHOR_TWITTER.sub('', author)
        # replace special characters with space
        author = trim(AUTHOR_REPLACE_JOIN.sub(' ', author))
        author = AUTHOR_REMOVE_NICKNAME.sub('', author)
        # remove special characters
        author = AUTHOR_REMOVE_SPECIAL.sub('', author)
        author = AUTHOR_PREFIX.sub('', author)
        author = AUTHOR_REMOVE_NUMBERS.sub('', author)
        author = AUTHOR_REMOVE_PREPOSITION.sub('', author)
        # skip empty or improbably long strings
        if len(author) == 0 or (
            # simple heuristics, regex or vowel tests also possible
            ' ' not in author and '-' not in author and len(author) >= 50
            ):
            continue
        # title case
        if not author[0].isupper() or sum(1 for c in author if c.isupper()) < 1:
            author = author.title()
        # safety checks
        if author not in new_authors and (len(new_authors) == 0 or all(new_author not in author for new_author in new_authors)):
            new_authors.append(author)
    if len(new_authors) == 0:
        return current_authors
    return '; '.join(new_authors).strip('; ')


def normalize_tags(tags):
    '''Remove special characters of tags'''
    tags = CLEAN_META_TAGS.sub(r'', trim(unescape(tags)))
    return ", ".join(filter(None, tags.split(", ")))