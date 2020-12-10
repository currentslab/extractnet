import io
import json
import os

import pytest

from extractnet import extract_content, extract_comments, extract_content_and_comments
from extractnet.blocks import simple_tokenizer
from extractnet.util import evaluation_metrics

FIXTURES = os.path.join('test', 'datafiles')


@pytest.fixture(scope="module")
def html():
    with io.open(os.path.join(FIXTURES, "models_testing.html"), mode="rt") as f:
        html_ = f.read()
    return html_


def test_models(html):
    pass

def test_content_and_content_comments_extractor(html):
    pass

def test_content_and_content_comments_extractor_blocks(html):
    """
    The content and content/comments extractor should return proper blocks
    """
    pass