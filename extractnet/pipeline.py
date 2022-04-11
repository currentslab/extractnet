import os
import logging
import numpy as np
import dateparser
from sklearn.base import BaseEstimator, ClassifierMixin
from .util import get_and_union_features, get_module_res, fix_encoding
from .nn_models import NewsNet
from .name_crf import AuthorExtraction
from .nn_models import NewsNet


class Extractor(BaseEstimator, ClassifierMixin):

    def __init__(self, author_extractor=None, content_extractor=None):
        if author_extractor is None:
            author_extractor = AuthorExtraction()
        if content_extractor is None:
            content_extractor = NewsNet()

        self.author_extractor = author_extractor
        self.content_extractor = content_extractor
        self.output_attributes = self.content_extractor.label_order

    @staticmethod
    def from_pretrained(directory=None):
        if directory is None:
            directory = get_module_res('models')
        nn_weight_path = os.path.join(directory, 'news_net.onnx')
        embedding_path = os.path.join(directory, 'char_embedding.joblib')
        crf_path = os.path.join(directory, 'crf.joblib')

        return Extractor(
            AuthorExtraction(embedding_path, crf_path),
            NewsNet(model_weight=nn_weight_path)
        )

    def extract(self, html, encoding=None, as_blocks=False, extract_target=None, debug=True):
        output = self.content_extractor.predict(html)
        if isinstance(output, dict):
            return self.postprocess(output)

        return [ self.postprocess(o) for o in output]

    def postprocess(self, output):
        results = {}
        if 'author' in output and len(output['author']) > 0:
            author_text, confidence = output['author'][0]
            results['rawAuthor'] = author_text
            results['authorConfidence'] = confidence
            results['author'] = self.author_extractor(author_text)
        
        if 'date' in output and len(output['date']) > 0:
            for date_text, confidence in output['date']:
                date = None
                try:
                    date = dateparser.parse(date_text)
                except Exception as err:
                    logging.error("date parsing failed, error : {}".format(err))
                if date is not None:
                    results['rawDate'] = date_text
                    results['dateConfidence'] = confidence
                    results['date'] = date

        for attribute, value in output.items():
            if attribute in ['author', 'date']:
                continue
            if isinstance(value, str):
                results[attribute] = value
            else:
                # is list of tuple (string, float) format
                results[attribute] = [val[0] for val in value ]
        return results