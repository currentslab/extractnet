# pylint:disable-msg=E0611,I1101
"""
Module bundling functions related to HTML and text processing.
"""
## This file is available from https://github.com/adbar/trafilatura
## under GNU GPL v3 license

# import csv
import logging
import re
import socket
import sys
from lxml import etree, html
from functools import lru_cache
import urllib
import urllib.parse
import json
import urllib.request
from bs4 import BeautifulSoup as bs

LOGGER = logging.getLogger(__name__)

# collect_ids=False, default_doctype=False, huge_tree=True,
HTML_PARSER = html.HTMLParser(remove_comments=True, remove_pis=True, encoding='utf-8')
RECOVERY_PARSER = html.HTMLParser(remove_comments=True, remove_pis=True)

UNICODE_WHITESPACE = re.compile(r'\u00A0|\u1680|\u2000|\u2001|\u2002|\u2003|\u2004|\u2005|\u2006|\u2007|\u2008|\u2009|\u200a|\u2028|\u2029|\u202F|\u205F|\u3000')

NO_TAG_SPACE = re.compile(r'(?<![p{P}>])\n')
SPACE_TRIMMING = re.compile(r'\s+', flags=re.UNICODE|re.MULTILINE)

NOPRINT_TRANS_TABLE = {
    i: None for i in range(0, sys.maxunicode + 1) if not chr(i).isprintable() and not chr(i) in (' ', '\t', '\n')
}

# Check https://regex101.com/r/A326u1/5 for reference
DOMAIN_FORMAT = re.compile(
	r"(?:^(\w{1,255}):(.{1,255})@|^)" # http basic authentication [optional]
	r"(?:(?:(?=\S{0,253}(?:$|:))" # check full domain length to be less than or equal to 253 (starting after http basic auth, stopping before port)
	r"((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+" # check for at least one subdomain (maximum length per subdomain: 63 characters), dashes in between allowed
	r"(?:[a-z0-9]{1,63})))" # check for top level domain, no dashes allowed
	r"|localhost)" # accept also "localhost" only
	r"(:\d{1,5})?", # port [optional]
	re.IGNORECASE
)
SCHEME_FORMAT = re.compile(
	r"^(http|hxxp|ftp|fxp)s?$", # scheme: http(s) or ftp(s)
	re.IGNORECASE
)

SPLIT_TOKENS = re.compile(r'[,|、]')

def re_xpath(self, path):
    return self.xpath(path, namespaces={
        're': 'http://exslt.org/regular-expressions'})
html.HtmlElement.re_xpath = re_xpath


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
            LOGGER.error('parsed tree length: %s, wrong data type or not valid HTML', len(tree))
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