from multiprocessing.sharedctypes import Value
import re
from urllib.parse import ParseResult, parse_qs, urlencode, urlparse
from tld import get_tld

NETLOC_RE = re.compile(r'(?<=\w):(?:80|443|8000|8080|5000)')
TYPICAL = re.compile(r'/+')
DOMAIN_PREFIX = re.compile(r'^www[0-9]*\.')

URL_DATE = [
    re.compile(r'(\d{4})\/(\d{1,2}|oct|jan|feb|mar|may|jun|jul|aug|sep|nov|dec|apr)\/(?:(\d{2})\/)'),
    re.compile(r'(\d{4})\/(\d{1,2}|oct|jan|feb|mar|may|jun|jul|aug|sep|nov|dec|apr)\/'),
    re.compile(r'(\d{4})-(\d{1,2}|oct|jan|feb|mar|may|jun|jul|aug|sep|nov|dec|apr)\/(?:(\d{2})\/)'),
    re.compile(r'\/(\d{4})\/'),
]

SMONTH_TO_NUM = [ '','jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec' ]
def url_date_token(url):
    return URL_DATE.find(url)

def parse_url_date(token):
    '''
        supported format
        2022/oct/25/
        2022/10/25/
        2022/10/
        2022/
    '''
    year, month, day = -1, -1, -1
    if len(token) == 3:
        year_str, month_str, day_str = token
        year = int(year_str)
        day = int(day_str)
        if month_str in SMONTH_TO_NUM:
            month = SMONTH_TO_NUM.index(month_str)
        else:
            month = int(month_str)
    elif len(token) == 2:
        year_str, month_str = token
        year = int(year_str)
        if month_str in SMONTH_TO_NUM:
            month = SMONTH_TO_NUM.index(month_str)
        else:
            month = int(month_str)
    else:
        if len(token[0]) == 4:
            year = int(token[0])
        elif len(token[0]) == 2: # not quite sure
            month = int(token[0])

    return year, month, day

def date_updater(url_date_token, date):

    year = url_date_token[0]
    if year > 100 and date.year != year:
        date = date.replace(year = year)

    month = url_date_token[1]
    if month > 0 and month < 13 and date.month != month:
        try:
            date = date.replace(month=month)
        except ValueError: # when month=2
            pass

    day = url_date_token[2]
    if day > 0 and day < 32 and day != date.day:
        try:
            date = date.replace(day = day)
        except ValueError: 
            # february or 31 on months which doesn't exist
            date = date.replace(day = day-1)

    return date

def validate_date(url, date):
    for url_date_re in URL_DATE:
        match = url_date_re.findall(url)
        if len(match):
            break

    if len(match) == 0:
        return date

    token = match[0]
    if not isinstance(token, tuple):
        token = (token,)

    date_tuple = parse_url_date(token)
    return date_updater(date_tuple, date)

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