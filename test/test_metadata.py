import io
import os
from shutil import rmtree
import tempfile

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
