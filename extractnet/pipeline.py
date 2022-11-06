import os
import logging
import numpy as np
import dateparser
from sklearn.base import BaseEstimator, ClassifierMixin
from .metadata_extraction.metadata import extract_metadata

from .compat import unicode_
from .util import priority_merge, get_module_res, remove_empty_keys, attribute_sanity_check
from .nn_models import NewsNet
from .name_crf import AuthorExtraction
from .nn_models import NewsNet


class Extractor(BaseEstimator, ClassifierMixin):

    def __init__(self, author_extractor=None, content_extractor=None, postprocess=[],
            meta_postprocess=[]):
        if author_extractor is None:
            author_extractor = AuthorExtraction()
        if content_extractor is None:
            content_extractor = NewsNet()
        self.meta_postprocess_pipelines = meta_postprocess
        self.has_meta_pos = len(meta_postprocess) > 0

        self.postprocess_pipelines = postprocess
        self.has_post = len(postprocess) > 0
        
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

    @staticmethod
    def extract_one_meta(document):
        meta_data = extract_metadata(document)
        meta_data = remove_empty_keys(meta_data)

        return meta_data

    def __call__(self, html, **kwargs):
        return self.extract(html, **kwargs)

    def extract(self, html, 
        encoding=None, 
        as_blocks=False,
        extract_target=None, 
        debug=False, 
        metadata_mining=True, 
        **kwargs):
        
        if isinstance(html, (str, bytes, unicode_, np.unicode_)):
            documents_meta_data = {}
            if metadata_mining:
                documents_meta_data = self.extract_one_meta(html)
                if self.has_meta_pos:
                    for pipeline in self.meta_postprocess_pipelines:
                        meta_post_result = pipeline(html)
                        documents_meta_data = priority_merge(meta_post_result, documents_meta_data)
        else: # must be a list
            documents_meta_data = []
            if metadata_mining:
                for document in html:
                    document_meta_data = self.extract_one_meta(document)
                    if self.has_meta_pos:
                        for pipeline in self.meta_postprocess_pipelines:
                            meta_post_result = pipeline(document)
                            document_meta_data = priority_merge(meta_post_result, document_meta_data)

                    documents_meta_data.append(document_meta_data)
            else:
                documents_meta_data = [{}] * len(html)

        output = self.content_extractor.predict(html)
        if isinstance(output, dict):
            return self.postprocess(html, output, documents_meta_data, **kwargs)

        return [ self.postprocess(h, o, meta, **kwargs) for h, o, meta in zip(html, output, documents_meta_data)]

    def postprocess(self, html, output, meta, **kwargs):
        results = {}
        if 'author' in output and len(output['author']) > 0:
            author_text, confidence = output['author'][0]
            results['rawAuthor'] = author_text
            results['authorConfidence'] = float(confidence)
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
            if isinstance(value, str) or value is None:
                results[attribute] = value
            else:
                # is list of tuple (string, float) format
                results[attribute] = [val[0] for val in value ]
        
        results = priority_merge(results, meta)

        if self.has_post:
            for pipeline in self.postprocess_pipelines:
                post_ml_results_ = pipeline(html, results)
                results = priority_merge(post_ml_results_, results)

        sanity_check_params = {}
        if 'url' in kwargs:
            sanity_check_params['url'] = kwargs['url']
        elif 'url' in results:
            sanity_check_params['url'] = results['url']

        return attribute_sanity_check(results, **sanity_check_params)
