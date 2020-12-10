from extractnet.blocks import Blockifier, PartialBlock, BlockifyError
from extractnet import features
from extractnet.util import load_pickled_model
from extractnet.hybrid_extractor import Extractor

_LOADED_MODELS = {}


def extract_content(html, encoding=None, as_blocks=False):
    pass

def extract_comments(html, encoding=None, as_blocks=False):
    pass

def extract_content_and_comments(html, encoding=None, as_blocks=False):
    pass