from .extractor import MultiExtractor
from .metadata_extraction.metadata import extract_metadata
from .compat import string_, str_cast, unicode_
from .util import get_and_union_features, convert_segmentation_to_text
from .sequence_tagger.models import word2features

import os
from sklearn.base import BaseEstimator
import joblib
import numpy as np
import dateparser

EXTRACTOR_DIR = __file__.replace('/hybrid_extractor.py','')

def merge_results(r1, r2):

    for key in r2.keys():
        if key not in r1:
            r1[key] = r2[key]
        elif isinstance(r1[key], str) and isinstance(r2[key], str):
            r1[key] = [r1[key], r2[key]]
        elif isinstance(r1[key], str) and isinstance(r2[key], list):
            r1[key] = r2[key] + [r1[key]]
        elif isinstance(r1[key], list) and isinstance(r2[key], str):
            r1[key] = r1[key] + [r2[key]]
        elif isinstance(r1[key], list) and isinstance(r2[key], list):
            r1[key] += r2[key]
    return r1

def remove_empty_keys(r1):
    for key in list(r1.keys()):
        if r1[key] is None:
            r1.pop(key)
    return r1

class Extractor(BaseEstimator):


    def __init__(self, 
            stage1_classifer=None,
            author_classifier=None, 
            date_classifier=None,
            author_embeddings=None,
            author_tagger=None, 
            data_prob_threshold=0.5,
            author_prob_threshold=0.5,
            ):
        '''
            For inference use only
        '''
        if stage1_classifer is None:
            stage1_classifer = os.path.join(EXTRACTOR_DIR, 'models/final_extractor.pkl.gz')
        if author_classifier is None:
            author_classifier = os.path.join(EXTRACTOR_DIR, 'models/author_extractor.pkl.gz')

        if date_classifier is None:
            date_classifier = os.path.join(EXTRACTOR_DIR, 'models/datePublishedRaw_extractor.pkl.gz')
        
        if author_embeddings is None:
            author_embeddings = os.path.join(EXTRACTOR_DIR, 'models/char_embedding.joblib')
        
        if author_tagger is None:
            author_tagger = os.path.join(EXTRACTOR_DIR, 'models/crf.joblib')



        self.author_clf = joblib.load(author_classifier)
        self.date_clf = joblib.load(date_classifier)

        if isinstance(stage1_classifer, str):
            self.stage1_clf = MultiExtractor.from_pretrained(stage1_classifer)
        else:
            self.stage1_clf = stage1_classifer

        self.data_prob_threshold = data_prob_threshold
        self.author_prob_threshold = author_prob_threshold

        self.author_embedding = joblib.load(author_embeddings)
        self.author_tagger = joblib.load(author_tagger)

    def post_process(self, results):
        '''
        Normalize and tidy some results
        '''
        if 'author' in results:
            results['rawAuthor'] = results['author']
            results['authorList'] = []
            if isinstance(results['rawAuthor'], list):
                for author_txt in results['rawAuthor']:
                    results['authorList'] += self.extract_author(author_txt)
            elif isinstance(results['rawAuthor'], str):
                results['authorList'] = self.extract_author(results['rawAuthor'])
            if len(results['authorList']) == 0:
                results['authorList'] = [ results['rawAuthor'] ]
            results.pop('author')

        if 'date' in results:
            results['rawDate'] = results['date']
            results['date'] = dateparser.parse(results['rawDate'])

        return results

    def extract(self, documents, 
            extract_content=True,
            extract_headlines=True,
            encoding='utf-8', 
            as_blocks=False, 
            metadata_mining=True
        ):

        ml_fallback = {
            'extract_content': extract_content,
            'extract_headlines': extract_headlines,
            'extract_author': False,
            'extract_breadcrumbs': False,
            'extract_description': False,
            'extract_date': False,
        }

        if isinstance(documents, (str, bytes, unicode_, np.unicode_)):
            documents_meta_data = {}
            if metadata_mining:
                documents_meta_data, meta_ml_fallback = self.extract_one_meta(documents)
                ml_fallback.update(meta_ml_fallback)
        else:
            documents_meta_data = []
            if metadata_mining:
                for document in documents:
                    document_meta_data, meta_ml_fallback = self.extract_one_meta(document)
                    ml_fallback.update(meta_ml_fallback)
            else:
                documents_meta_data = [{}] * len(documents)

        ml_results = self.ml_extract(documents, encoding=encoding, as_blocks=as_blocks, **ml_fallback)
        # we assume the accuracy of meta data is always better than machine learning
        if isinstance(documents, (str, bytes, unicode_, np.unicode_)):
            ml_results = self.post_process( 
                merge_results(ml_results, documents_meta_data)
            )
            return ml_results
        else:
            for idx, meta_data in enumerate(documents_meta_data):
                ml_results[idx] = self.post_process( 
                    merge_results(ml_results[idx], meta_data)
                )
            return ml_results

    @staticmethod
    def extract_one_meta(document):
        ml_fallback = {}
        meta_data = extract_metadata(document)
        meta_data = remove_empty_keys(meta_data)

        if 'author' not in meta_data or (meta_data['author'] is None):
            ml_fallback['extract_author'] = True
        if 'description' not in meta_data  or (meta_data['description'] is None):
            ml_fallback['extract_description'] = True
        if 'tags' not in meta_data  or (meta_data['tags'] is None):
            ml_fallback['extract_breadcrumbs'] = True
        if 'date' not in meta_data  or (meta_data['date'] is None):
            ml_fallback['extract_date'] = True
        return meta_data, ml_fallback

    @staticmethod
    def format_index_feature(
            extract_content=True,
            extract_headlines=True,
            extract_description=True,
            extract_breadcrumbs=True,
        ):
        extract_index = {
            'content': MultiExtractor.FIELD_INDEX['content'] if extract_content else None,
            'headlines': MultiExtractor.FIELD_INDEX['headlines'] if extract_headlines else None,
            'description': MultiExtractor.FIELD_INDEX['description'] if extract_description else None,
            'breadcrumbs': MultiExtractor.FIELD_INDEX['breadcrumbs'] if extract_breadcrumbs else None,
        }

        extract_target_index = sorted([ index for _, index in extract_index.items() if index is not None ])

        target_order = [ (order_idx, MultiExtractor.INVERTED_INDEX[field_idx])  \
            for order_idx, field_idx in enumerate(extract_target_index) ]

        return extract_target_index, target_order


    def ml_extract(self, html, as_blocks=False,
            extract_content=True,
            extract_author=True,
            extract_breadcrumbs=True,
            extract_headlines=True,
            extract_description=True,
            extract_date=True,
            encoding='utf-8',
            ):

        extract_target_index, target_order = self.format_index_feature(
            extract_content=extract_content, 
            extract_headlines=extract_headlines,
            extract_description=extract_description,
            extract_breadcrumbs=extract_breadcrumbs,
        )

        multi_blocks, full_blocks = self.stage1_clf.extract(html, 
            encoding=encoding, as_blocks=True, return_blocks=True, 
            extract_target=extract_target_index)

        # str_cast(b'\n'.join(blocks[ind].text for ind in np.flatnonzero(preds)
        results = {}
        for order_idx, field_name in target_order:
            if field_name == 'breadcrumbs':
                results[field_name ] = [ str_cast(block.text) for block in multi_blocks[order_idx]]
            else:
                results[field_name ] = str_cast(b'\n'.join([ block.text for block in multi_blocks[order_idx]]))

        # full_blocks = multi_blocks[0]
        auth_feature = None
        if extract_author:
            auth_feature = self.stage1_clf.auth_feat.transform(full_blocks)
            auth_blocks = self.author_clf.predict_proba(auth_feature)

            if len(full_blocks) > 3:
                best_index = np.argmax(auth_blocks[:, 1])
                auth_prob = auth_blocks[best_index, 1]
                if auth_prob > self.author_prob_threshold:
                    results['author'] = str_cast(full_blocks[best_index].text)
                    # results['author'] = self.extract_author(results['rawAuthor'])

        if extract_date:
            # reuse if possible
            if auth_feature is None:
                auth_feature = self.stage1_clf.auth_feat.transform(full_blocks)

            date_blocks = self.date_clf.predict_proba(auth_feature)
            best_index = np.argmax(date_blocks[:, 1])
            date_prob = date_blocks[best_index, 1]
            date_found = False

            if date_prob > self.data_prob_threshold:
                date_found = True
                results['date'] = str_cast(full_blocks[best_index].text)
                # results['date'] = dateparser.parse(results['rawDate'])

        if as_blocks:
            results['raw_blocks'] = multi_blocks

        return results

    def extract_author(self, text):
        text = text.strip()
        embeddings = [word2features(text, i, self.author_embedding) for i in range(len(text))]
        y_pred = self.author_tagger.predict([embeddings])
        return convert_segmentation_to_text(y_pred[0], text)
