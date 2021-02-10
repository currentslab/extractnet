import re

METADATA_LIST = ['title', 'author', 'url', 'hostname', 'description', 'sitename', 'date', 'categories', 'tags', 'fingerprint', 'id']

HTMLDATE_CONFIG = {'extensive_search': False, 'original_date': True}

TITLE_REGEX = re.compile(r'(.+)?\s+[-|]\s+.*$')
JSON_AUTHOR_1 = re.compile(r'"author":[^}[]+?"name?\\?": ?\\?"([^"\\]+)|"author"[^}[]+?"names?".+?"([^"]+)|"author": ?\\?"([^"\\]+)"', re.DOTALL)
JSON_AUTHOR_2 = re.compile(r'"[Pp]erson"[^}]+?"names?".+?"([^"]+)', re.DOTALL)
JSON_AUTHOR_3 = re.compile(r'"author": ?\\?"([^"\\]+)"')

JSON_PUBLISHER = re.compile(r'"publisher":[^}]+?"name?\\?": ?\\?"([^"\\]+)', re.DOTALL)
JSON_CATEGORY = re.compile(r'"articleSection": ?"([^"\\]+)', re.DOTALL)
JSON_NAME = re.compile(r'"@type":"[Aa]rticle", ?"name": ?"([^"\\]+)', re.DOTALL)
JSON_HEADLINE = re.compile(r'"headline": ?"([^"\\]+)', re.DOTALL)

TEXT_AUTHOR_PATTERNS = [ '〔[^ ]*／[^ ]*報導〕', 
    '記者[^ ]*／[^ ]*報導〕', '記者[^ ]*日電〕', 
    '文／[^ ]* ', '記者[^ ]*／[^ ]*報導',  '（[^ ]*／[^ ]*報導）',
    '／記者[^ ]*報導', '記者[^ ]*／[^ ]*報導',
    '【[^ ]*專欄】', '【[^ ]*快報[^ ]*】', '【[^ ]*／[^ ]*】' ]

URL_COMP_CHECK = re.compile(r'https?://|/')

# blacklist author to trigger regex base matching code
# this allows you to call extract_author function
BLACKLIST_AUTHOR = ['udn', 'ETtoday新聞雲', 'ltn', '自由時報電子報']
