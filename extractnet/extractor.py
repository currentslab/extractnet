import logging

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.ensemble import ExtraTreesClassifier
import os
import dateparser
import joblib

from .compat import string_, str_cast, unicode_
from .util import get_and_union_features, convert_segmentation_to_text
from .blocks import TagCountReadabilityBlockifier
from .features.author import AuthorFeatures
from .sequence_tagger.models import word2features

from sklearn.base import clone

BASE_EXTRACTOR_DIR = __file__.replace('/extractor.py','')

class MultiExtractor(BaseEstimator, ClassifierMixin):
    """
        An sklearn-style classifier that extracts the main content (and/or comments)
        from an HTML document.

        Args:
            blockifier (``Blockifier``)
            features (str or List[str], ``Features`` or List[``Features``], or List[Tuple[str, ``Features``]]):
                One or more features to be used to transform blocks into a matrix of
                numeric values. If more than one, a :class:`FeatureUnion` is
                automatically constructed. See :func:`get_and_union_features`.
            model (:class:`ClassifierMixin`): A scikit-learn classifier that takes
                a numeric matrix of features and outputs a binary prediction of
                1 for content or 0 for not-content. If None, a :class:`ExtraTreesClassifier`
                with default parameters is used.
            to_extract (str or Sequence[str]): Type of information to extract from
                an HTML document: 'content', 'comments', or both via ['content', 'comments'].
            prob_threshold (float): Minimum prediction probability of a block being
                classified as "content" for it actually be taken as such.
            max_block_weight (int): Maximum weight that a single block may be given
                when training the extractor model, where weights are set equal to
                the number of tokens in each block.

        Note:
            If ``prob_threshold`` is not None, then ``model`` must implement the
                ``predict_proba()`` method.
    """

    FIELD_INDEX = {
        'content': 0,
        'description': 1,
        'headlines': 2,
        'breadcrumbs': 3
    }
    INVERTED_INDEX = { value: key for key, value in FIELD_INDEX.items() }

    def state_dict(self):

        return {
            'params': self.params,
            'pca': self.auth_feat.pca,
            'classifiers': self.classifiers
        }

    def __init__(self, blockifier=TagCountReadabilityBlockifier,
                 features=('kohlschuetter', 'weninger', 'readability'),
                 model=None,
                 css_tokenizer_path=None,
                 text_tokenizer_path=None,
                 num_labels=2, prob_threshold=0.5, max_block_weight=200,
                 features_type=None, author_feature_transforms=None):
        if css_tokenizer_path is None:
            css_tokenizer_path = os.path.join(BASE_EXTRACTOR_DIR, 'models/css_tokenizer.pkl.gz')
        if text_tokenizer_path is None:
            text_tokenizer_path = os.path.join(BASE_EXTRACTOR_DIR, 'models/text_tokenizer.pkl.gz')

        self.params = {
            'features': features,
            'num_labels': num_labels,
            'prob_threshold': prob_threshold,
            'max_block_weight': max_block_weight,
            'features_type': features_type,
        }

        self.blockifier = blockifier
        self.features = features
        css_tokenizer = joblib.load(css_tokenizer_path)
        text_tokenizer = joblib.load(text_tokenizer_path)

        if author_feature_transforms is None:
            author_feature_transforms = AuthorFeatures(css_tokenizer, text_tokenizer,
                    features=('kohlschuetter', 'weninger', 'readability', 'css'),
                )

        self.auth_feat = author_feature_transforms

        self.feature_func = [
            self.auth_feat,
            self.features,
        ]

        # initialize model
        if model is None:
            self.model = ExtraTreesClassifier()
        elif isinstance(model, list):
            self.classifiers = model
        else:
            self.classifiers = [ clone(model)  for _ in range(num_labels)]
        if features_type is None:
            self.features_type = [0]*len(self.classifiers)
        else:
            self.features_type = features_type
        self.target_features = list(range(len(self.classifiers)))
        self.prob_threshold = prob_threshold
        self.max_block_weight = max_block_weight
        self._positive_idx = None

    @staticmethod
    def from_pretrained(filename):
        checkpoint  =  joblib.load(filename)

        extractor = MultiExtractor(model=checkpoint['classifiers'],
                **checkpoint['params'])
        extractor.auth_feat.pca = checkpoint['pca']
        return extractor

    @property
    def features(self):
        return self._features

    @features.setter
    def features(self, feats):
        self._features = get_and_union_features(feats)

    @staticmethod
    def validate(labels, block_groups, weights=None):

        clean_labels, clean_weights, clean_block_groups = [], [], []
        # iterate through all documents
        for idx, label in enumerate(labels):
            # make sure all labels, weights, block size can be matched
            if weights is None and len(label) == len(block_groups[idx]):
                clean_labels.append(labels[idx])
                clean_block_groups.append(block_groups[idx])
            elif len(label) == len(block_groups[idx]) and len(label) == len(weights[idx]):
                clean_labels.append(labels[idx])
                clean_weights.append(weights[idx])
                clean_block_groups.append(block_groups[idx])

        if weights is None:
            return np.array(clean_labels), np.array(clean_block_groups)
        return np.array(clean_labels), np.array(clean_weights), np.array(clean_block_groups)


    def fit(self, documents, labels, weights=None, init_models=None, **kwargs):
        """
        Fit :class`Extractor` features and model to a training dataset.

        Args:
            blocks (List[Block])
            labels (``np.ndarray``)
            weights (``np.ndarray``)

        Returns:
            :class`Extractor`
        """
        mask, block_groups = [], []
        for doc in documents:
            block_groups.append(self.blockifier.blockify(doc))
            mask.append(self._has_enough_blocks(block_groups[-1]))

        block_groups = np.array(block_groups, dtype=object)
        # filter out mask and validate each document size
        if weights is None:
            labels, block_groups = self.validate(np.array(labels)[mask],  block_groups[mask])
        else:
            labels, weights, block_groups = self.validate(
                np.array(labels)[mask],
                block_groups[mask],
                np.array(weights)[mask])

            weights = np.concatenate(weights)

        labels = np.concatenate(labels)

        complex_feat_mat = self.auth_feat.fit_transform(
                        np.concatenate(block_groups)
                    )

        if 1 in self.features_type:
            features_mat = np.concatenate([self.features.fit_transform(blocks)
                                       for blocks in block_groups])

        for idx, clf in enumerate(self.classifiers):
            print('fit model ', idx)
            input_feat = complex_feat_mat if self.features_type[idx] == 0 else features_mat
            print(input_feat.shape)

            init_model = None
            if not(init_models is None) and isinstance(init_models, list):
                init_model = init_models[idx]

            if weights is None:
                self.classifiers[idx] = clf.fit(input_feat, labels[:, idx], 
                    init_model=init_model, **kwargs)
            else:
                self.classifiers[idx] = clf.fit(input_feat, labels[:, idx], 
                    sample_weight=weights[:, idx], init_model=init_model, **kwargs)

        return self

    def get_html_multi_labels_weights(self, data, attribute_indexes=[0], not_skip_indexes = []):
        """
        Gather the html, labels, and weights of many files' data.
        Primarily useful for training/testing an :class`Extractor`.

        Args:
            data: Output of :func:`extractnet.data_processing.prepare_all_data`.

        Returns:
            Tuple[List[Block], np.array(int), np.array(int)]: All blocks, all
                labels, and all weights, respectively.
        """
        all_html = []
        all_labels = []
        all_weights = []
        for row in data:
            html = row[0]
            attributes = row[1:]
            skip = False

            multi_label = []
            multi_weights = []

            for attribute_idx in attribute_indexes:
                labels, weights = self._get_labels_and_weights(attributes, attribute_idx=attribute_idx)
                multi_label.append(labels)
                multi_weights.append(weights)

            if skip:
                continue

            if len(html) > 0 and len(multi_label) == len(attribute_indexes):
                all_html.append(html)
                all_labels.append(np.stack(multi_label, -1))
                all_weights.append(np.stack(multi_weights, -1))

        return np.array(all_html, dtype=object), np.array(all_labels, dtype=object), np.array(all_weights, dtype=object)

    def _has_enough_blocks(self, blocks):
        if len(blocks) < 3:
            # logging.warning(
            #     'extraction failed: too few blocks (%s)', len(blocks))
            return False
        return True

    def _get_labels_and_weights(self, attributes, attribute_idx):
        """
        Args:
            attributes List[(Tuple[np.array[int], np.array[int], List[str]])] : label, weights, string

        Returns:
            Tuple[np.array[int], np.array[int], List[str]]
        """
        # extract content and comments

        labels = attributes[attribute_idx][0]

        weights = attributes[attribute_idx][1]

        if self.max_block_weight is None:
            weights = np.minimum(weights, self.max_block_weight)

        return labels, weights

    def extract(self, html, encoding='utf-8', as_blocks=False, extract_target=None, return_blocks=False):
        """
        Extract the main content and/or comments from an HTML document and
        return it as a string or as a sequence of block objects.

        Args:
            html (str): HTML document as a string.
            encoding (str): Encoding of ``html``. If None (encoding unknown), the
                original encoding will be guessed from the HTML itself.
            as_blocks (bool): If False, return the main content as a combined
                string; if True, return the content-holding blocks as a list of
                block objects.

        Returns:
            str or List[Block]
        """
        multi_preds, blocks = self.predict(html, encoding=encoding, return_blocks=True, extract_target=extract_target)
        outputs = []
        for preds in multi_preds.T:
            if as_blocks is False:
                outputs.append(str_cast(b'\n'.join(blocks[ind].text for ind in np.flatnonzero(preds))))
            else:
                outputs.append([blocks[ind] for ind in np.flatnonzero(preds)])
        if return_blocks:
            return outputs, blocks
        return outputs

    def predict(self, documents, **kwargs):
        """
        Predict class (content=1 or not-content=0) of the blocks in one or many
        HTML document(s).

        Args:
            documents (str or List[str]): HTML document(s)

        Returns:
            ``np.ndarray`` or List[``np.ndarray``]: array of binary predictions
                for content (1) or not-content (0).
        """
        if isinstance(documents, (str, bytes, unicode_, np.unicode_)):
            return self._predict_one(documents, **kwargs)
        else:
            return np.concatenate([self._predict_one(doc, **kwargs) for doc in documents])


    def _predict_one(self, document, encoding='utf-8', return_blocks=False, extract_target=None):
        """
        Predict class (content=1 or not-content=0) of each block in an HTML
        document.

        Args:
            documents (str): HTML document
            extract_target (list): List of target index to extract

        Returns:
            ``np.ndarray``: array of binary predictions for content (1) or
            not-content (0).
        """
        if extract_target is None:
            extract_target = self.target_features
        # blockify
        blocks = self.blockifier.blockify(document, encoding=encoding)
        # get features
        try:
            # features = self.features.transform(blocks)
            features = self.features.transform(blocks)
            input_feat = [self.auth_feat.transform(blocks, encoding=encoding), features]
            # features = np.concatenate([features, auth_feat], -1)
        except KeyError: # Can't make features, predict no content
            preds = np.zeros((len(blocks)))
        # make predictions
        else:
            if self.prob_threshold is None:
                multi_output = []
                for cls_idx, cls in enumerate(self.classifiers):
                    if cls_idx in extract_target:
                        feature_idx = self.features_type[cls_idx]
                        output = cls.predict(input_feat[feature_idx])
                        multi_output.append(output)

                preds = np.stack(multi_output).T
            else:
                multi_output = []
                for cls_idx, cls in enumerate(self.classifiers):
                    if cls_idx in extract_target:
                        feature_idx = self.features_type[cls_idx]
                        _positive_idx = (
                            self._positive_idx or list(self.classifiers[cls_idx].classes_).index(1))
                        preds = cls.predict_proba(input_feat[feature_idx]) > self.prob_threshold
                        preds = preds[:, _positive_idx].astype(int)
                        multi_output.append(preds)
                preds = np.stack(multi_output).T

        if return_blocks:
            return preds, blocks
        else:
            return preds


class CascadeExtractor(BaseEstimator, ClassifierMixin):


    def __init__(self, stage1_classifer=None,
            author_classifier=None, date_classifier=None,
            author_embeddings= 'extractnet/models/char_embedding.joblib',
            author_tagger='extractnet/models/crf.joblib'):
        '''
            For inference use only
        '''
        if isinstance(stage1_classifer, str):
            self.stage1_classifer = MultiExtractor.from_pretrained(stage1_classifer)
        else:
            self.stage1_classifer = stage1_classifer
        stage1_field_mapping = [
            'full_content',
            'article_content',
            'headline',
            'breadcrumbs'
        ]


        self.author_classifier = author_classifier
        self.date_classifier = date_classifier

        self.author_embedding = joblib.load(author_embeddings)
        self.author_tagger = joblib.load(author_tagger)


    def extract(self, html, encoding=None, as_blocks=False, extract_target=None, debug=True):
        multi_blocks, full_blocks = self.stage1_classifer.extract(html, 
            encoding=encoding, as_blocks=True, return_blocks=True)

        # str_cast(b'\n'.join(blocks[ind].text for ind in np.flatnonzero(preds)
        results = {
            'article': str_cast(b'\n'.join([ block.text for block in multi_blocks[0]])),
            'headlines': str_cast(b'\n'.join([ block.text for block in multi_blocks[1]])),
            'description': str_cast(b'\n'.join([ block.text for block in multi_blocks[2]])),
            'bread_crumbs' : [ str_cast(block.text) for block in multi_blocks[3]],
        }

        # full_blocks = multi_blocks[0]
        auth_feature = self.stage1_classifer.auth_feat.transform(full_blocks)
        auth_blocks = self.author_classifier.predict_proba(auth_feature)
        date_blocks = self.date_classifier.predict_proba(auth_feature)

        if len(full_blocks) > 3:
            best_index = np.argmax(auth_blocks[:, 1])
            auth_prob = auth_blocks[best_index, 1]
            if auth_prob > 0.5:
                results['rawAuthor'] = str_cast(full_blocks[best_index].text)
                results['author'] = self.extract_author(results['rawAuthor'])

        best_index = np.argmax(date_blocks[:, 1])
        date_prob = date_blocks[best_index, 1]
        date_found = False

        if date_prob > 0.5:
            date_found = True
            results['rawDate'] = str_cast(full_blocks[best_index].text)
            results['date'] = dateparser.parse(results['rawDate'])

        if as_blocks:
            results['raw_blocks'] = multi_blocks

        if debug:
            results['all_blocks'] = full_blocks
            results['full_content_blocks'] = full_content_blocks
            results['author_prob'] = auth_blocks

        return results

    def extract_author(self, text):
        text = text.strip()
        embeddings = [word2features(text, i, self.author_embedding) for i in range(len(text))]
        y_pred = self.author_tagger.predict([embeddings])
        return convert_segmentation_to_text(y_pred[0], text)