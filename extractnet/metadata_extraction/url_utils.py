import re
from urllib.parse import ParseResult, parse_qs, urlencode, urlparse
from tld import get_tld

NETLOC_RE = re.compile(r'(?<=\w):(?:80|443|8000|8080|5000)')
TYPICAL = re.compile(r'/+')
DOMAIN_PREFIX = re.compile(r'^www[0-9]*\.')

def extract_domain(url, blacklist=None):
    # new code: Python >= 3.6 with tld module
    tldinfo = get_tld(url, as_object=True, fail_silently=True)
    # invalid input OR domain TLD blacklist
    if tldinfo is None:
        return None
    return DOMAIN_PREFIX.sub('', tldinfo.fld)


def url_is_valid(url):
    try:
        parsed_url = urlparse(url)
    except ValueError:
        return False, None

    if not bool(parsed_url.scheme) or parsed_url.scheme not in (
        'http',
        'https',
    ):
        return False, None
    if len(parsed_url.netloc) < 5 or (
            parsed_url.netloc.startswith('www.') and len(parsed_url.netloc) < 8
        ):
        return False, None

    return True, parsed_url

def url_normalizer(url):
    '''
        return a string of url, return None if failed
    '''
    if isinstance(url, ParseResult):
        parsed_url = url
    else:
        try:
            parsed_url = urlparse(url)
        except AttributeError:
            return None

    if parsed_url.port is not None and parsed_url.port in (80, 443):
        parsed_url = parsed_url._replace(netloc=NETLOC_RE.sub('', parsed_url.netloc))
    newpath = TYPICAL.sub('/', parsed_url.path)
    parsed_url = parsed_url._replace(
                    scheme=parsed_url.scheme.lower(),
                    netloc=parsed_url.netloc.lower(),
                    path=newpath,
                    fragment=parsed_url.fragment
                    )
    # strip query section
    if len(parsed_url.query) > 0:
        qdict = parse_qs(parsed_url.query)
        newqdict = {}
        for qelem in sorted(qdict.keys()):
            teststr = qelem.lower()
            # insert
            newqdict[qelem] = qdict[qelem]
        newstring = urlencode(newqdict, doseq=True)
        parsed_url = parsed_url._replace(query=newstring)
    # rebuild
    return parsed_url.geturl()