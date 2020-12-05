import re
import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from extractnet.util import get_and_union_features
from sklearn.decomposition import PCA

class AuthorFeatures(BaseEstimator, TransformerMixin):
    """
    An sklearn-style transformer that takes an ordered sequence of ``Block`` objects
    and returns a 2D array of Author-based features, where each value can be varies
    """
    __name__ = 'author'

    # tokens that we search for in each block's CSS attribute
    # first 'id', then 'class'

    attribute_tags = (
        'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'html', 'p', 'span', 'table', 'author',
    )
    tag_attributes = (
        'rel', 'id', 'class', 'itemprop', 'content', 'name'
    )
    name_attributes = re.compile(r'[author|name|publisher]')

    def __init__(self, vectorizer, text_vectorizer,
            features=('kohlschuetter', 'weninger', 'readability', 'css'),
            pca_n_components=10
        ):
        self.vectorizer = vectorizer
        self.text_vectorizer = text_vectorizer
        self.feature = get_and_union_features(features)
        self.pca = PCA(n_components=pca_n_components)


    def fit(self, blocks, y=None):
        """
        This method returns the current instance unchanged, since no fitting is
        required for this ``Feature``. It's here only for API consistency.
        """
        feature_vecs = np.stack([np.concatenate((self.transform_block(block, idx, len(blocks)), dragnet_feat[idx]) )  for idx, block in enumerate(blocks) ])
        self.pca.fit(feature_vecs[:, 8:])
        return self

    def fit_transform(self, blocks, y=None):
        dragnet_feat = self.feature.transform(blocks)
        feature_vecs = np.stack([np.concatenate((self.transform_block(block, idx, len(blocks)), dragnet_feat[idx]) )  for idx, block in enumerate(blocks) ])
        pca_feat = self.pca.fit_transform(feature_vecs[:, 8:])
        feature_vecs = np.concatenate([feature_vecs[:, :8], pca_feat ], 1)
        # feature_vecs = [self.transform_block(block)  for idx, block in enumerate(blocks) ]
        return np.concatenate([feature_vecs, dragnet_feat], 1)

    def transform_block(self, block, block_pos, total_blocks, encoding='utf-8'):
        css_text = ''
        other_text = ''
        if b'css' in block.css:
            css_text += block.css[b'css'].decode(encoding)+' '
        if b'id' in block.css:
            css_text += block.css[b'id'].decode(encoding)+' '

        # tag_multi_hot is useless by catboost
        # 'rel', 'id', 'class', 'itemprop', 'content', 'name'

        # css TF-IDF : useless
        features = self.vectorizer.transform([ css_text+' '+other_text ]).toarray().flatten()
        # content text TFIDF
        text_features = self.text_vectorizer.transform([block.text]).toarray().flatten()

        handcraft_features = [0, 0, 0, 0, 0, 0, 0, 0, 0]
        if 'author' in css_text.lower() or 'author' in other_text.lower():
            handcraft_features[0] = 1

        if b'block_start_element' in block.features:
            tag_type = block.features[b'block_start_element'].tag
            if tag_type in self.attribute_tags:
                handcraft_features[1] = self.attribute_tags.index(tag_type) + 1

        handcraft_features[2] = len(css_text+other_text)
        handcraft_features[3] = len(block.text)

        if self.name_attributes.search(css_text):
            handcraft_features[5] = 1
        if self.name_attributes.search(other_text):
            handcraft_features[4] = 1
        handcraft_features[6] = block.link_density / block.text_density
        handcraft_features[7] = block_pos / total_blocks
        handcraft_features[8] = total_blocks
        # handcraft_features : 0-3, tag_multi_hot: 4-9
        return np.concatenate((handcraft_features, text_features, features))

    def transform(self, blocks, y=None, encoding='utf-8'):
        """
        Transform an ordered of blocks into a 2D features matrix with
        shape (num blocks, num features).

        Args:
            blocks (List[Block]): as output by :class:`Blockifier.blockify`
            y (None): This isn't used, it's only here for API consistency.

        Returns:
            `np.ndarray`: 2D array of shape (num blocks, num CSS attributes),
                where values are either 0 or 1, indicating the absence or
                presence of a given token in a CSS attribute on a given block.
        """
        dragnet_feat = self.feature.transform(blocks)
        feature_vecs = np.stack([np.concatenate((self.transform_block(block, idx, len(blocks), encoding=encoding), dragnet_feat[idx]) )  for idx, block in enumerate(blocks) ])
        pca_feat = self.pca.transform(feature_vecs[:, 8:])
        feature_vecs = np.concatenate([feature_vecs[:, :8], pca_feat ], 1)
        # feature_vecs = [self.transform_block(block)  for idx, block in enumerate(blocks) ]
        return np.concatenate([feature_vecs, dragnet_feat], 1)
