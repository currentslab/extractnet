"""
Functions needed to scrape metadata from JSON-LD format.
"""

import json
import re
from .constant import (
    JSON_AUTHOR_3, JSON_AUTHOR_1, JSON_AUTHOR_2, JSON_AUTHOR_REMOVE,
    JSON_PUBLISHER, JSON_CATEGORY, JSON_HEADLINE,
    JSON_MATCH, JSON_ARTICLE_SCHEMA, JSON_PUBLISHER_SCHEMA,
    JSON_NAME
)
from .utils import normalize_authors, trim



def extract_json(schema, metadata):
    '''Parse and extract metadata from JSON-LD data'''
    if isinstance(schema, dict):
        schema = [schema]

    for parent in filter(None, schema):
        if '@context' not in parent or not isinstance(parent['@context'], str) or parent['@context'][-10:].lower() != 'schema.org':
            continue
        if '@graph' in parent:
            parent = parent['@graph'] if isinstance(parent['@graph'], list) else [parent['@graph']]
        elif '@type' in parent and isinstance(parent['@type'], str) and 'liveblogposting' in parent['@type'].lower() and 'liveBlogUpdate' in parent:
            parent = parent['liveBlogUpdate'] if isinstance(parent['liveBlogUpdate'], list) else [parent['liveBlogUpdate']]
        else:
            parent = schema

        for content in filter(None, parent):
            # try to extract publisher
            if 'publisher' in content and 'name' in content['publisher']:
                metadata['sitename'] = content['publisher']['name']

            if '@type' not in content:
                continue
            if isinstance(content["@type"], list):
                # some websites are using ['Person'] as type
                content_type = content["@type"][0].lower()
            else:
                content_type = content["@type"].lower()

            if content_type in JSON_PUBLISHER_SCHEMA:
                for candidate in ("name", "alternateName"):
                    if candidate in content and content[candidate] is not None:
                        if metadata['sitename'] is None or (len(metadata['sitename']) < len(content[candidate]) and content_type != "webpage"):
                            metadata['sitename'] = content[candidate]
                        if metadata['sitename'] is not None and metadata['sitename'].startswith('http') and not content[candidate].startswith('http'):
                            metadata['sitename'] = content[candidate]

            elif content_type == "person":
                if 'name' in content and content['name'] is not None and not content['name'].startswith('http'):
                    metadata['name'] = normalize_authors(metadata['name'] if 'name' in metadata else None, content['name'])

            elif content_type in JSON_ARTICLE_SCHEMA:
                # author and person
                if 'author' in content:
                    list_authors = content['author']
                    if isinstance(list_authors, str):
                        # try to convert to json object
                        try:
                            list_authors = json.loads(list_authors)
                        except json.JSONDecodeError:
                            # it is a normal string
                            metadata['name'] = normalize_authors(metadata['name'] if 'name' in metadata else None, 
                                                list_authors)

                    if not isinstance(list_authors, list):
                        list_authors = [list_authors]
                    for author in list_authors:
                        if '@type' not in author or author['@type'] == 'Person':
                            # error thrown: author['name'] can be a list (?)
                            if 'name' in author and author['name'] is not None:
                                author_name = author['name']
                                if isinstance(author_name, list):
                                    author_name = '; '.join(author_name).strip('; ')

                                metadata['name'] = normalize_authors(metadata['name'] if 'name' in metadata else None, 
                                                                    author_name
                                                                )
                            elif 'givenName' in author is not None and 'familyName' in author:
                                name = [author['givenName'], author['additionalName'], author['familyName']]
                                metadata['name'] = normalize_authors(
                                    metadata['name'] if 'name' in metadata else None, 
                                    ' '.join([n for n in name if n is not None])
                                )
                # category
                if metadata['categories'] is None and 'articleSection' in content:
                    if isinstance(content['articleSection'], str):
                        metadata['categories'] = [content['articleSection']]
                    else:
                        metadata['categories'] = list(filter(None, content['articleSection']))

                # try to extract title
                if metadata['title'] is None:
                    if 'name' in content and content_type == 'article':
                        metadata['title'] = content['name']
                    elif 'headline' in content:
                        metadata['title'] = content['headline']
    return metadata


def extract_json_author(elemtext, regular_expression):
    '''Crudely extract author names from JSON-LD data'''
    authors = None
    author_match = regular_expression.search(elemtext)
    while author_match is not None:
        if author_match[1] and ' ' in author_match[1]:
            authors = normalize_authors(authors, author_match[1])
            elemtext = regular_expression.sub(r'', elemtext, count=1)
            author_match = regular_expression.search(elemtext)
        else:
            break
    return authors or None


def extract_json_parse_error(elem, metadata):
    '''Crudely extract metadata from JSON-LD data'''
    # author info
    element_text_author = JSON_AUTHOR_REMOVE.sub('', elem)
    if any(JSON_MATCH.findall(element_text_author)):
        metadata['author'] = extract_json_author(elem.text, JSON_AUTHOR_1)
        if metadata['author'] is None:
            metadata['author'] = extract_json_author(elem.text, JSON_AUTHOR_2)
        if metadata['author'] is None:
            metadata['author'] = extract_json_author(elem.text, JSON_AUTHOR_3)
    # try to extract publisher
    if '"publisher"' in elem:
        match_pub = JSON_PUBLISHER.search(elem)
        if match_pub and ',' not in match_pub[1]:
            candidate = normalize_json(match_pub[1])
            if metadata['sitename'] is None or len(metadata['sitename']) < len(candidate):
                metadata['sitename'] = candidate
            if metadata['sitename'].startswith('http') and not candidate.startswith('http'):
                metadata['sitename'] = candidate
    # category
    if '"articleSection"' in elem:
        match_jsoncat = JSON_CATEGORY.search(elem)
        if match_jsoncat:
            metadata['categories'] = [normalize_json(match_jsoncat[1])]
    # try to extract title
    if '"name"' in elem and metadata['title'] is None:
        match_json_name = JSON_NAME.search(elem)
        if match_json_name:
            metadata['title'] = normalize_json(match_json_name[1])
    if '"headline"' in elem and metadata['title'] is None:
        match_head = JSON_HEADLINE.search(elem)
        if match_head:
            metadata['title'] = normalize_json(match_head[1])
    # exit if found
    return metadata


def normalize_json(inputstring):
    'Normalize unicode strings and trim the output'
    if '\\' in inputstring:
        return trim(inputstring.encode().decode('unicode-escape'))
    return trim(inputstring)