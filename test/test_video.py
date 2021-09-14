import io
import os
from shutil import rmtree
import tempfile

import pytest
from extractnet.metadata_extraction.video import get_advance_fields

FIXTURES = os.path.join('test', 'datafiles')

def test_video_none():
    # do not extract google tag manager
    html_file = os.path.join(FIXTURES,'video_example_false.html')
    with open(html_file, 'r') as f:
        html_txt = f.read()
    results = get_advance_fields(html_txt)

    assert results['video'] == None

def test_yt_video_none():
    # do not extract google tag manager
    html_file = os.path.join(FIXTURES,'video_example_yt.html')
    with open(html_file, 'r') as f:
        html_txt = f.read()
    results = get_advance_fields(html_txt)
    assert results['video'] == 'https://www.youtube.com/watch?v=test_example'