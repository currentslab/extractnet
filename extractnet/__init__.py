from extractnet.blocks import Blockifier, PartialBlock, BlockifyError
from extractnet import features
from extractnet.pipeline import Extractor
from extractnet.settings import __version__

_LOADED_MODELS = {}

def extract_news(html, encoding=None, as_blocks=False):
    if 'news_extraction' not in _LOADED_MODELS:
        _LOADED_MODELS['news_extraction'] = Extractor()

    return _LOADED_MODELS['news_extraction'].extract(html)

