import io
import os
from shutil import rmtree
import tempfile

import pytest
from extractnet.metadata_extraction.video import get_advance_fields

FIXTURES = os.path.join('test', 'datafiles')

def test_audio():
    html_file = os.path.join(FIXTURES,'audio_example.html')
    with open(html_file, 'r') as f:
        html_txt = f.read()
    results = get_advance_fields(html_txt)
    assert results['audio'] != None