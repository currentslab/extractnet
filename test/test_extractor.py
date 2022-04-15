import io
import os

import numpy as np
import pytest
from extractnet import Extractor


@pytest.fixture(scope="module")
def html():
    fname = os.path.join("test", "datafiles", "models_testing.html")
    with io.open(fname, mode="rt") as f:
        html_ = f.read()
    return html_

@pytest.fixture(scope="module")
def tag_html():
    fname = os.path.join("test", "datafiles", "tags_test.html")
    with io.open(fname, mode="rt") as f:
        html_ = f.read()
    return html_


def test_extractor(html):
    extractor = Extractor()
    results = extractor(html, metadata_mining=False)
    assert 'content' in results

def test_extractor_w_meta(tag_html):
    extractor = Extractor()
    results = extractor(tag_html, metadata_mining=True)
    assert 'content' in results
    assert 'og_properties' in results
