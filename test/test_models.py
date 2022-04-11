import io
import json
import os

import pytest

from extractnet import extract_news
from extractnet.blocks import simple_tokenizer
from extractnet.util import evaluation_metrics

FIXTURES = os.path.join('test', 'datafiles')


@pytest.fixture(scope="module")
def html():
    with io.open(os.path.join(FIXTURES, "models_testing.html"), mode="rt") as f:
        html_ = f.read()
    return html_


def test_models(html):
    results = extract_news(html)

    assert 'content' in results
    assert 'headline' in results