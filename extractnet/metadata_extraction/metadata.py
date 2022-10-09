"""
Module bundling all functions needed to scrape metadata from webpages.


This file is available from https://github.com/adbar/trafilatura
under GNU GPL v3 license

"""


import itertools
import logging
import re
import json
from htmldate import find_date
from lxml import html
from urllib.parse import ParseResult
from .json_ld import extract_json_parse_error, extract_json
from .url_utils import url_normalizer, extract_domain, url_is_valid
from .metaxpaths import author_xpaths, categories_xpaths, tags_xpaths, title_xpaths
from .video import get_advance_fields
from .utils import load_html, trim, split_tags, check_authors, unescape, line_processing
from .constant import (
    TEXT_LICENSE_REGEX, LICENSE_REGEX,
    METADATA_LIST, TITLE_REGEX,  HTMLDATE_CONFIG_EXTENSIVE, HTMLDATE_CONFIG_FAST,
    JSON_MINIFY,
    TEXT_AUTHOR_PATTERNS, URL_COMP_CHECK, BLACKLIST_AUTHOR
)
LOGGER = logging.getLogger(__name__)
logging.getLogger('htmldate').setLevel(logging.WARNING)


def criteria_fulfilled(metadata):
    for key in ['author', 'sitename', 'categories', 'title', 'name']:
        if key not in metadata:
            return False
    if all([metadata['author'], metadata['sitename'], metadata['categories'], metadata['title'], metadata['name']]):
        return True
    return False

def extract_meta_json(tree, metadata):
    '''Parse and extract metadata from JSON-LD data'''
    for elem in tree.xpath('.//script[@type="application/ld+json" or @type="application/settings+json"]'):
        if not elem.text:
            continue
        element_text = JSON_MINIFY.sub(r'\1', elem.text)
        try:
            schema = json.loads(element_text)
            metadata = extract_json(schema, metadata)
        except json.JSONDecodeError:
            metadata = extract_json_parse_error(element_text, metadata)

        if criteria_fulfilled(metadata):
            break

    return metadata



def extract_json_author(elemtext, regular_expression):
    '''Crudely extract author names from JSON-LD data'''
    json_authors = list()
    mymatch = regular_expression.search(elemtext)

    while mymatch is not None:
        if mymatch.group(1):
            json_authors.append(trim(mymatch.group(1)))
            elemtext = regular_expression.sub(r'', elemtext, count=1)
            mymatch = regular_expression.search(elemtext)
        else:
            break
    # final trimming
    if json_authors:
        return '; '.join(json_authors).strip('; ')
    return None





def extract_opengraph(tree):
    '''Search meta tags following the OpenGraph guidelines (https://ogp.me/)'''
    title, author, url, description, site_name = (None,) * 5
    # detect OpenGraph schema
    og_full_property = {}
    for elem in tree.xpath('.//head/meta[starts-with(@property, "og:")]'):
        # safeguard
        if not elem.get('content'):
            continue
        # site name
        og_full_property[elem.get('property')[3:]] = elem.get('content')
        if elem.get('property') == 'og:site_name':
            site_name = elem.get('content')
        # blog title
        elif elem.get('property') == 'og:title':
            title = elem.get('content')
        # orig URL
        elif elem.get('property') == 'og:url':
            if url_is_valid(elem.get('content'))[0] is True:
                url = elem.get('content')
        # description
        elif elem.get('property') == 'og:description':
            description = elem.get('content')
        # og:author
        elif elem.get('property') in ('og:author', 'og:article:author'):
            author = elem.get('content')
        # og:type
        #elif elem.get('property') == 'og:type':
        #    pagetype = elem.get('content')
        # og:locale
        #elif elem.get('property') == 'og:locale':
        #    pagelocale = elem.get('content')
    return trim(title), trim(author), trim(url), trim(description), trim(site_name), og_full_property


def examine_meta(tree):
    '''Search meta tags for relevant information'''
    metadata = dict.fromkeys(METADATA_LIST)
    # bootstrap from potential OpenGraph tags
    title, author, url, description, site_name, og_full_property = extract_opengraph(tree)
    # test if all return values have been assigned
    if all((title, author, url, description, site_name)):  # if they are all defined
        metadata['title'], metadata['author'], metadata['url'], metadata['description'], metadata['sitename'] = title, author, url, description, site_name
        metadata['og_properties'] = og_full_property
        return metadata
    tags = []
    # skim through meta tags
    og_properties = {}
    for elem in tree.iterfind('.//head/meta[@content]'):
        # content
        if not elem.get('content'):
            continue
        content_attr = elem.get('content')
        # image info
        # ...
        # property
        if 'property' in elem.attrib:
            # no opengraph a second time
            if elem.get('property').startswith('og:'):
                og_properties[elem.get('property')[3:] ] = content_attr
            if elem.get('property') == 'article:tag':
                tags.append(content_attr)
            elif elem.get('property') in ('author', 'article:author'):
                if author is None:
                    author = content_attr
        # name attribute
        elif 'name' in elem.attrib:
            name_attr = elem.get('name').lower()
            # author
            if name_attr in ('author', 'byl', 'dc.creator', 'dcterms.creator', 'sailthru.author'):  # twitter:creator
                if author is None:
                    author = content_attr
            # title
            elif name_attr in ('title', 'dc.title', 'dcterms.title', 'fb_title', 'sailthru.title', 'twitter:title'):
                if title is None:
                    title = content_attr
            # description
            elif name_attr in ('description', 'dc.description', 'dcterms.description', 'dc:description', 'sailthru.description', 'twitter:description'):
                if description is None:
                    description = content_attr
            # site name
            elif name_attr in ('publisher', 'dc.publisher', 'dcterms.publisher', 'twitter:site', 'application-name') or 'twitter:app:name' in elem.get('name'):
                if site_name is None:
                    site_name = content_attr
            # url
            elif name_attr == 'twitter:url':
                if url is None and url_is_valid(content_attr)[0] is True:
                    url = content_attr
            # keywords
            elif name_attr == 'keywords': # 'page-topic'
                tags.append(content_attr)
        elif 'itemprop' in elem.attrib:
            if elem.get('itemprop') == 'author':
                if author is None:
                    author = content_attr
            elif elem.get('itemprop') == 'description':
                if description is None:
                    description = content_attr
            elif elem.get('itemprop') == 'headline':
                if title is None:
                    title = content_attr
            # to verify:
            #elif elem.get('itemprop') == 'name':
            #    if title is None:
            #        title = elem.get('content')
        # other types
        else:
            if not 'charset' in elem.attrib and not 'http-equiv' in elem.attrib and not 'property' in elem.attrib:
                LOGGER.debug(html.tostring(elem, pretty_print=False, encoding='unicode').strip())
    
    tags_ = list(itertools.chain.from_iterable([split_tags(t) for t in tags]))

    metadata.update({
        'title': title,
        'author': author,
        'url': url, 
        'description':description, 
        'site_name': site_name,
        'tags': tags_,
        'og_properties': og_properties
    })
    return metadata


def extract_metainfo(tree, expressions, len_limit=200):
    '''Extract meta information'''
    # try all XPath expressions
    for expression in expressions:
        # examine all results
        i = 0
        for elem in tree.xpath(expression):
            content = elem.text_content()
            if content and len(content) < len_limit:
                return trim(content)
            i += 1
        if i > 1:
            LOGGER.debug('more than one invalid result: %s %s', expression, i)
    return None


def extract_title(tree):
    '''Extract the document title'''
    title = None
    # only one h1-element: take it
    h1_results = tree.xpath('//h1')
    if len(h1_results) == 1:
        return h1_results[0].text_content()
    # extract using x-paths
    title = extract_metainfo(tree, title_xpaths)
    if title is not None:
        return title
    # extract using title tag
    try:
        title = tree.xpath('//head/title')[0].text_content()
        # refine
        mymatch = TITLE_REGEX.match(title)
        if mymatch:
            title = mymatch.group(1)
        return title
    except IndexError:
        LOGGER.warning('no main title found')
    # take first h1-title
    if h1_results:
        return h1_results[0].text_content()
    # take first h2-title
    try:
        title = tree.xpath('//h2')[0].text_content()
    except IndexError:
        LOGGER.warning('no h2 title found')
    return title


def parse_license_element(element, strict=False):
    '''Probe a link for identifiable free license cues.
       Parse the href attribute first and then the link text.'''
   # look for Creative Commons elements
    match = LICENSE_REGEX.search(element.get('href'))
    if match:
        return 'CC ' + match[1].upper() + ' ' + match[2]
    if element.text is not None:
        # just return the anchor text without further ado
        if strict is False:
            return trim(element.text)
        # else: check if it could be a CC license
        match = TEXT_LICENSE_REGEX.search(element.text)
        if match:
            return match[0]
    return None

def extract_license(tree):
    '''Search the HTML code for license information and parse it.'''
    result = None
    # look for links labeled as license
    for element in tree.findall('.//a[@rel="license"][@href]'):
        result = parse_license_element(element, strict=False)
        if result is not None:
            break
    # probe footer elements for CC links
    if result is None:
        for element in tree.xpath(
            './/footer//a[@href]|.//div[contains(@class, "footer") or contains(@id, "footer")]//a[@href]'
        ):
            result = parse_license_element(element, strict=True)
            if result is not None:
                break
    return result

def extract_author(tree):
    '''Extract the document author(s)'''
    author = extract_metainfo(tree, author_xpaths, len_limit=75)
    if author:
        # simple filters for German and English
        author = re.sub(r'^([a-zäöüß]+(ed|t))? ?(by|von) ', '', author, flags=re.IGNORECASE)
        author = re.sub(r'\d.+?$', '', author)
        author = re.sub(r'[^\w]+$|( am| on)', '', trim(author))
        author = author.title()
    if author is None:
        for text_author_pattern in TEXT_AUTHOR_PATTERNS:
            matches = tree.re_xpath("//*[re:match( text(), '{}' )]".format(text_author_pattern))
            if len(matches) > 0:
                match_text = matches[0].text
                author = re.search(text_author_pattern, match_text).group(0)
                break

    return author


def extract_url(tree, default_url=None):
    '''Extract the URL from the canonical link'''
    # https://www.tutorialrepublic.com/html-reference/html-base-tag.php
    # default url as fallback
    url = default_url
    # try canonical link first
    element = tree.find('.//head//link[@rel="canonical"]')
    if element is not None and URL_COMP_CHECK.match(element.attrib['href']):
        url = element.attrib['href']
    # try default language link
    else:
        for element in tree.iterfind('.//head//link[@rel="alternate"]'):
            if 'hreflang' in element.attrib and element.attrib['hreflang'] is not None and element.attrib['hreflang'] == 'x-default':
                if URL_COMP_CHECK.match(element.attrib['href']):
                    LOGGER.debug(html.tostring(element, pretty_print=False, encoding='unicode').strip())
                    url = element.attrib['href']
    # add domain name if it's missing
    if url is not None and url.startswith('/'):
        for element in tree.iterfind('.//head//meta[@content]'):
            if 'name' in element.attrib:
                attrtype = element.attrib['name']
            elif 'property' in element.attrib:
                attrtype = element.attrib['property']
            else:
                continue
            if attrtype.startswith('og:') or attrtype.startswith('twitter:'):
                domain_match = re.match(r'https?://[^/]+', element.attrib['content'])
                if domain_match:
                    # prepend URL
                    url = domain_match.group(0) + url
                    break
    # sanity check: don't return invalid URLs
    if url is not None:
        validation_result, parsed_url = url_is_valid(url)
        if isinstance(parsed_url, ParseResult):
            url = parsed_url.geturl()
        elif validation_result is False:
            url = None
        elif isinstance(url, str) and len(parsed_url) > 0:
            url = url_normalizer(parsed_url)

    return url


def extract_sitename(tree):
    '''Extract the name of a site from the main title (if it exists)'''
    title_elem = tree.find('.//head/title')
    if title_elem is not None:
        try:
            match_site = re.search(r'^.*?[-|]\s+(.*)$', title_elem.text)
            if match_site:
                return match_site.group(1)
        except (AttributeError, TypeError):
            pass
    return None


def extract_catstags(metatype, tree):
    '''Find category and tag information'''
    results = []
    regexpr = '/' + metatype + '/'
    if metatype == 'category':
        xpath_expression = categories_xpaths
    else:
        xpath_expression = tags_xpaths
    # search using custom expressions
    for catexpr in xpath_expression:
        for elem in tree.xpath(catexpr):
            if 'href' in elem.attrib and re.search(regexpr, elem.attrib['href']):
                results.append(elem.text_content())
        if results:
            break
    # category fallback
    if metatype == 'category' and not results:
        element = tree.find('.//head//meta[@property="article:section"]')
        if element is not None:
            results.append(element.attrib['content'])
    tags = list(itertools.chain.from_iterable([split_tags(trim(x)) for x in results if x is not None]))
    return tags


def extract_metadata(filecontent, default_url=None, date_config=None, fastmode=False, author_blacklist=BLACKLIST_AUTHOR):
    """Main process for metadata extraction.
    Args:
        filecontent: HTML code as string.
        default_url: Previously known URL of the downloaded document.
        date_config: Provide extraction parameters to htmldate as dict().
        author_blacklist: Provide a blacklist of Author Names as set() to filter out authors.
    Returns:
        A dict() containing the extracted metadata information or None.
    """
    # init
    if author_blacklist is None:
        author_blacklist = set()
    elif isinstance(author_blacklist, list):
        author_blacklist = set(author_blacklist)

    # load contents
    tree = load_html(filecontent)
    if tree is None:
        return {}
    # initialize dict and try to strip meta tags
    metadata = examine_meta(tree)

    advance_fields = get_advance_fields(filecontent)
    if advance_fields:
        for field in ['audio', 'video']:
            if field in advance_fields:
                metadata[field] = advance_fields[field]
            else:
                metadata[field] = None
    if metadata['author'] is not None and len(author_blacklist) > 0:
        metadata['author'] = check_authors(metadata['author'], author_blacklist)
    if metadata['author'] is None or URL_COMP_CHECK.match(metadata['author']):
        metadata['author'] = extract_author(tree)
    # fix: try json-ld metadata and override
    try:
        metadata = extract_meta_json(tree, metadata)
    # todo: fix bugs in json_metadata.py
    except TypeError as err:
        LOGGER.warning('error in JSON metadata extraction: %s', err)
    # title
    if metadata['title'] is None:
        metadata['title'] = extract_title(tree)
    # url
    if metadata['url'] is None:
        metadata['url'] = extract_url(tree, default_url)
    # hostname
    if metadata['url'] is not None:
        metadata['hostname'] = extract_domain(metadata['url'])
    # extract date with external module htmldate
    if date_config is None:
        # decide on fast mode HTMLDATE_CONFIG_EXTENSIVE, HTMLDATE_CONFIG_FAST
        if fastmode is False:
            date_config = HTMLDATE_CONFIG_EXTENSIVE
        else:
            date_config = HTMLDATE_CONFIG_FAST
    date_config['url'] = metadata['url']
    metadata['date'] = find_date(tree, **date_config)

    if metadata['sitename'] is not None:
        if metadata['sitename'].startswith('@'):
            # scrap Twitter ID
            metadata['sitename'] = re.sub(r'^@', '', metadata['sitename'])
        # capitalize
        try:
            if not '.' in metadata['sitename'] and not metadata['sitename'][0].isupper():
                # make every first char upper
                metadata['sitename'] = metadata['sitename'].title()
        # fix for empty name
        except IndexError:
            LOGGER.warning('sitename extraction error')
            if metadata['url']:
                url_link_match = re.match(r'https?://(?:www\.|w[0-9]+\.)?([^/]+)', metadata['url'])
                if url_link_match:
                    metadata['sitename'] = url_link_match.group(1)

    elif metadata['url']:
        url_link_match = re.match(r'https?://(?:www\.|w[0-9]+\.)?([^/]+)', metadata['url'])
        if url_link_match:
            metadata['sitename'] = url_link_match.group(1)

    # categories
    if not metadata['categories']:
        metadata['categories'] = extract_catstags('category', tree)
    # tags
    if not metadata['tags']:
        metadata['tags'] = extract_catstags('tags', tree)
    # license
    metadata['license'] = extract_license(tree)
    # safety checks

    return clean_and_trim(metadata)


def clean_and_trim(metadata):
    'Limit text length and trim the attributes.'
    for key in metadata.keys():
        value = metadata[key]
        if isinstance(value, str):
            # length
            if len(value) > 10000:
                new_value = value[:9999] + '…'
                metadata[key] = new_value

            # HTML entities, remove spaces and control characters
            value = line_processing(unescape(value))
            metadata[key] = value
    return metadata

