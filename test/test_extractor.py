import io
import os

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from extractnet import Extractor
from extractnet.blocks import TagCountNoCSSReadabilityBlockifier
from extractnet.util import get_and_union_features
from extractnet.compat import str_cast


@pytest.fixture(scope="module")
def html():
    fname = os.path.join("test", "datafiles", "models_testing.html")
    with io.open(fname, mode="rt") as f:
        html_ = f.read()
    return html_


def test_extractor(html):
    pass