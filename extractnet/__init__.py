__version__ = '2.0.0'

from extractnet.blocks import Blockifier, PartialBlock, BlockifyError
from extractnet import features
from extractnet.pipeline import Extractor

_LOADED_MODELS = {}

def extract_content(html, encoding=None, as_blocks=False):
    if 'news_extraction' not in _LOADED_MODELS:
        _LOADED_MODELS['news_extraction'] = Extractor()

    return _LOADED_MODELS['news_extraction'].predict(html)

def extract_comments(html, encoding=None, as_blocks=False):
    pass

def extract_content_and_comments(html, encoding=None, as_blocks=False):
    pass