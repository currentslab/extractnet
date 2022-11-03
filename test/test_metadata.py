import io
import os
from re import L
from shutil import rmtree
import tempfile
from wsgiref import validate

import pytest
from extractnet.metadata_extraction.metadata import extract_metadata

FIXTURES = os.path.join('test', 'datafiles')

def test_meta_extraction():
    html_file = os.path.join(FIXTURES, 'video_example_yt.html')
    with open(html_file, 'r') as f:
        html_txt = f.read()
    results = extract_metadata(html_txt)
    assert results['title'] != None
    assert results['author'] != None
    assert results['video'] != None



from extractnet.metadata_extraction.url_utils import validate_date


def test_date_validate_from_url():

    from datetime import datetime
    default_date = datetime(2022, 1, 1, 12, 11, 10)
    urls = [
        ('http://rssfeeds.usatoday.com/~/718271584/0/usatodaycomsports-topstories~New-body-camera-footage-shows-Hope-Solos-DWI-arrest-from-March/',default_date),
        ('http://rssfeeds.pnj.com/~/718260410/0/pensacola/news~Anglers-and-pedestrians-delighted-that-Palafox-Pier-has-reopened-in-Pensacola-PHOTOS/', default_date),
        ('https://www.msn.com/en-gb/news/newsbirmingham/man-taken-to-hospital-with-burns-after-lithium-battery-explodes-in-great-barr-house/ar-AA12JUmH', datetime(2022, 1, 1)),
        ('https://www.washingtontimes.com/news/2022/oct/27/lucianne-goldberg-bill-clinton-impeachment-figure-/', datetime(2022, 10, 27)),
        ('https://www.azcentral.com/picture-gallery/news/local/arizona/2017/10/18/remembering-arizona-leaders-who-have-died/106769086/', datetime(2017, 10, 18)),
        ('https://www.cnn.com/2017/01/23/politics/cdc-climate-conference-canceled-trump-administration/index.html', datetime(2017, 1, 23)),
        ('https://www.cnn.com/2017/05/29/tennis/french-open-tennis-djokovic-agassi-nadal/index.html', datetime(2017, 5, 29)),
        ('https://dfw.cbslocal.com/2015/01/police-officers-give-sick-boy-a-b-day-surprise/', datetime(2015, 1, 1)),
        ('https://www.cnn.com/2022/2/29/politics/cdc-climate-conference-canceled-trump-administration/index.html', datetime(2022, 2, 28)),
        ('http://www.apnewsarchive.com/2015/Even-70-years-later-Allied-firebombing-of-Dresden-still-fresh-in-survivor-s-mind/id-1862c9192bdc46289e303f2c443eb13b', datetime(2015, 1, 1)),
        ('http://www.china.org.cn/world/Off_the_Wire/2022-10/08/content_78455811.htm', datetime(2022, 10, 8)),
    ]

    for (url, target_date) in urls:
        fixed_date = validate_date(url, default_date)
        assert fixed_date.date() == target_date.date()

