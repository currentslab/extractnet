import re
import sys
from lxml import html

METADATA_LIST = ['title', 'author', 'url', 'hostname', 'description', 'sitename', 'date', 'categories', 'tags', 'fingerprint', 'id']

HTMLDATE_CONFIG = {'extensive_search': False, 'original_date': True}

TITLE_REGEX = re.compile(r'(.+)?\s+[-|]\s+.*$')
JSON_AUTHOR_1 = re.compile(r'"author":[^}[]+?"name?\\?": ?\\?"([^"\\]+)|"author"[^}[]+?"names?".+?"([^"]+)|"author": ?\\?"([^"\\]+)"', re.DOTALL)
JSON_AUTHOR_2 = re.compile(r'"[Pp]erson"[^}]+?"names?".+?"([^"]+)', re.DOTALL)
JSON_AUTHOR_3 = re.compile(r'"author": ?\\?"([^"\\]+)"')
JSON_AUTHOR_REMOVE = re.compile(r',?(?:"\w+":?[:|,\[])?{?"@type":"(?:[Ii]mageObject|[Oo]rganization|[Ww]eb[Pp]age)",[^}[]+}[\]|}]?')
JSON_ARTICLE_SCHEMA = {"article", "backgroundnewsarticle", "blogposting", "medicalscholarlyarticle", "newsarticle", "opinionnewsarticle", "reportagenewsarticle", "scholarlyarticle", "socialmediaposting", "liveblogposting"}
JSON_PUBLISHER_SCHEMA = {"newsmediaorganization", "organization", "webpage", "website"}

JSON_PUBLISHER = re.compile(r'"publisher":[^}]+?"name?\\?": ?\\?"([^"\\]+)', re.DOTALL)
JSON_CATEGORY = re.compile(r'"articleSection": ?"([^"\\]+)', re.DOTALL)
JSON_NAME = re.compile(r'"@type":"[Aa]rticle", ?"name": ?"([^"\\]+)', re.DOTALL)
JSON_HEADLINE = re.compile(r'"headline": ?"([^"\\]+)', re.DOTALL)
JSON_MATCH = re.compile(r'"author":|"person":', flags=re.IGNORECASE)

TEXT_AUTHOR_PATTERNS = [ '〔[^ ]*／[^ ]*報導〕', 
    '記者[^ ]*／[^ ]*報導〕', '記者[^ ]*日電〕', 
    '文／[^ ]* ', '記者[^ ]*／[^ ]*報導',  '（[^ ]*／[^ ]*報導）',
    '／記者[^ ]*報導', '記者[^ ]*／[^ ]*報導', 
    '【[^ ]*專欄】', '【[^ ]*快報[^ ]*】', '【[^ ]*／[^ ]*】' ]

URL_COMP_CHECK = re.compile(r'https?://|/')
HTMLTITLE_REGEX = re.compile(r'^(.+)?\s+[-|]\s+(.+)$')  # part without dots?
URL_COMP_CHECK = re.compile(r'https?://')
HTML_STRIP_TAG = re.compile(r'(<!--.*?-->|<[^>]*>)')


HTMLDATE_CONFIG_FAST = {'extensive_search': False, 'original_date': True}
HTMLDATE_CONFIG_EXTENSIVE = {'extensive_search': True, 'original_date': True}
URL_COMP_CHECK = re.compile(r'https?://|/')
# blacklist author to trigger regex base matching code
# this allows you to call extract_author function
BLACKLIST_AUTHOR = set(['udn', 'ETtoday新聞雲', 'ltn', '自由時報電子報'])

JSON_MINIFY = re.compile(r'("(?:\\"|[^"])*")|\s')
LICENSE_REGEX = re.compile(r'/(by-nc-nd|by-nc-sa|by-nc|by-nd|by-sa|by|zero)/([1-9]\.[0-9])')
TEXT_LICENSE_REGEX = re.compile(r'(cc|creative commons) (by-nc-nd|by-nc-sa|by-nc|by-nd|by-sa|by|zero) ?([1-9]\.[0-9])?', re.I)

METANAME_AUTHOR = {
    'article:author','author', 'byl', 'citation_author',
    'dc.creator', 'dc.creator.aut', 'dc:creator',
    'dcterms.creator', 'dcterms.creator.aut', 'parsely-author',
    'sailthru.author', 'shareaholic:article_author_name'
}  # questionable: twitter:creator
METANAME_DESCRIPTION = {
    'dc.description', 'dc:description',
    'dcterms.abstract', 'dcterms.description',
    'description', 'sailthru.description', 'twitter:description'
}
METANAME_PUBLISHER = {
    'article:publisher', 'citation_journal_title', 'copyright',
    'dc.publisher', 'dc:publisher', 'dcterms.publisher',
    'publisher'
}  # questionable: citation_publisher
METANAME_TAG = {
    'citation_keywords', 'dcterms.subject', 'keywords', 'parsely-tags',
    'shareaholic:keywords', 'tags'
}
METANAME_TITLE = {
    'citation_title', 'dc.title', 'dcterms.title', 'fb_title',
    'parsely-title', 'sailthru.title', 'shareaholic:title',
    'title', 'twitter:title'
}
OG_AUTHOR = {'og:author', 'og:article:author'}
PROPERTY_AUTHOR = {'author', 'article:author'}
TWITTER_ATTRS = {'twitter:site', 'application-name'}

# also interesting: article:section & og:type

EXTRA_META = {'charset', 'http-equiv', 'property'}

AUTHOR_PREFIX = re.compile(r'^([a-zäöüß]+(ed|t))? ?(written by|words by|words|by|von|from) ', flags=re.IGNORECASE)
AUTHOR_REMOVE_NUMBERS = re.compile(r'\d.+?$')
AUTHOR_TWITTER = re.compile(r'@[\w]+')
AUTHOR_REPLACE_JOIN = re.compile(r'[._+]')
AUTHOR_REMOVE_NICKNAME = re.compile(r'["‘({\[’\'][^"]+?[‘’"\')\]}]')
AUTHOR_REMOVE_SPECIAL = re.compile(r'[^\w]+$|[:()?*$#!%/<>{}~]')
AUTHOR_REMOVE_PREPOSITION = re.compile(r'\b\s+(am|on|for|at|in|to|from|of|via|with|—|-)\s+(.*)', flags=re.IGNORECASE)
AUTHOR_EMAIL = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
AUTHOR_SPLIT = re.compile(r'/|;|,|\||&|(?:^|\W)[u|a]nd(?:$|\W)', flags=re.IGNORECASE)
AUTHOR_EMOJI_REMOVE = re.compile(
    "["u"\U0001F600-\U0001F64F" u"\U0001F300-\U0001F5FF" u"\U0001F680-\U0001F6FF" u"\U0001F1E0-\U0001F1FF"
    u"\U00002500-\U00002BEF" u"\U00002702-\U000027B0" u"\U000024C2-\U0001F251"
    u"\U0001f926-\U0001f937" u"\U00010000-\U0010ffff" u"\u2640-\u2642" u"\u2600-\u2B55" u"\u200d"
    u"\u23cf" u"\u23e9" u"\u231a" u"\ufe0f" u"\u3030" "]+", flags=re.UNICODE)

CLEAN_META_TAGS = re.compile(r'["\']')

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
UNICODE_ALIASES = {'utf-8', 'utf_8'}

LINES_TRIMMING = re.compile(r'(?<![p{P}>])\n', flags=re.UNICODE|re.MULTILINE)