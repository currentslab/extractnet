import io
import os

import numpy as np
import pytest
import joblib

from extractnet import Extractor


@pytest.fixture(scope="module")
def html():
    fname = os.path.join("test", "datafiles", "models_testing.html")
    with io.open(fname, mode="rt") as f:
        html_ = f.read()
    return html_


def test_extractor(html):
    extractor = Extractor()
    
    results = extractor.extract(html, metadata_mining=False)

    assert 'content' in results

