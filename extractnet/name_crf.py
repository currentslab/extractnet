import os
from sklearn.base import BaseEstimator
import joblib
import numpy as np
import dateparser
import logging
from .util import convert_segmentation_to_text, get_module_res
from .sequence_tagger.models import word2features


class AuthorExtraction(BaseEstimator):
    def __init__(self, author_embeddings=None,
            author_tagger=None):
        
        if author_embeddings is None:
            author_embeddings = get_module_res('models/char_embedding.joblib')

        if author_tagger is None:
            author_tagger = get_module_res('models/crf.joblib')

        self.author_embedding = joblib.load(author_embeddings)
        self.author_tagger = joblib.load(author_tagger)

    def __call__(self, text):
        if isinstance(text, list):
            return [ self.segment(t) for t in text]
        return self.segment(text)

    def segment(self, text):
        text = text.strip()
        embeddings = [word2features(text, i, self.author_embedding) for i in range(len(text))]
        y_pred = self.author_tagger.predict([embeddings])
        return convert_segmentation_to_text(y_pred[0], text)
