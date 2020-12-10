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
    auth_clf = joblib.load('extractnet/models/author_extractor.pkl.gz')
    date_clf = joblib.load('extractnet/models/datePublishedRaw_extractor.pkl.gz')
    extractor = Extractor('extractnet/models/final_extractor.pkl.gz', 
                                    auth_clf, date_clf)
    
    results = extractor.extract(html, metadata_mining=False)

    assert 'content' in results

