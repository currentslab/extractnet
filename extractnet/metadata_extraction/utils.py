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