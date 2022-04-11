import re

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin


class CSSFeatures(BaseEstimator, TransformerMixin):
    """
    An sklearn-style transformer that takes an ordered sequence of ``Block`` objects
    and returns a 2D array of CSS-based features, where each value is 0 or 1,
    depending on the absence or presence of certain tokens in a block's
    CSS id or class attribute.
    """
    __name__ = 'css'

    # tokens that we search for in each block's CSS attribute
    # first 'id', then 'class'
    attribute_tokens = (
        ('class',
         (
          'menu', 'widget', 'nav', 'top', 'content', 'breadcrumb', 'block', 'title',
          'button', 'header', 'ss', 'post', 'tag', 'line', 'foot', 'para', 'link',
          'published', 'date', 'modif', 'article', 'click', 'body', 'card', 'timestamp',
          'comment', 'meta', 'alt', 'time', 'depth', 'author', 'tool', 'keyword',
           'url', 'name', )
        ),
    )
    attribute_tags = (
        'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'html', 'p', 'span', 'table', 'author',
    )
    name_attributes = re.compile(r'(author)|(name)|(publisher)|(contribute)|(label)')
    ctx_attributes = re.compile(r'(By )|(記者)|(編輯)|(eporte)|(文)|( and )')
    ctx_symbol_attributes = re.compile(r'[／]')
    date_like = re.compile(r'[0-9一二三四五六七八九月年日]+')
    sentence_splits = re.compile(r'[.。,，]+')

    def fit(self, blocks, y=None):
        """
        This method returns the current instance unchanged, since no fitting is
        required for this ``Feature``. It's here only for API consistency.
        """
        return self
    
    def transform_block(self, block, encoding='utf-8'):
        css_text = ''
        text = block.text.decode(encoding)
        if b'css' in block.css:
            css_text += block.css[b'css'].decode(encoding)+' '
        if b'id' in block.css:
            css_text += block.css[b'id'].decode(encoding)+' '
        if b'class' in block.css:
            css_text += block.css[b'class'].decode(encoding)+' '
        if b'href' in block.css:
            css_text += block.css[b'href'].decode(encoding)+' '

        handcraft_features = [0, 0, 0, 0, 0, 0, 0, 0]
        if self.name_attributes.search(css_text):
            handcraft_features[0] = 1
        if self.ctx_attributes.search(text):
            handcraft_features[1] = 1
        if self.ctx_symbol_attributes.search(text):
            handcraft_features[2] = 1

        if b'block_start_element' in block.features:
            tag_type = block.features[b'block_start_element'].tag
            if tag_type in self.attribute_tags:
                handcraft_features[3] = self.attribute_tags.index(tag_type) + 1

        handcraft_features[4] = len(css_text)

        if self.date_like.search(text):
            handcraft_features[5] = 1

        if self.sentence_splits.search(text):
            handcraft_features[6] = 1

        handcraft_features[7] = len(text)

        return handcraft_features


    def transform(self, blocks, y=None):
        """
        Transform an ordered sequence of blocks into a 2D features matrix with
        shape (num blocks, num features).

        Args:
            blocks (List[Block]): as output by :class:`Blockifier.blockify`
            y (None): This isn't used, it's only here for API consistency.

        Returns:
            `np.ndarray`: 2D array of shape (num blocks, num CSS attributes),
                where values are either 0 or 1, indicating the absence or
                presence of a given token in a CSS attribute on a given block.
        """
        feature_vecs = []
        for block in blocks:
            feature_vec = []
            for attrib, tokens in self.attribute_tokens:
                if attrib not in block.css:
                    feature_vec += [0]*len(tokens)
                    continue

                for token in tokens:
                    if attrib in block.css and re.search(token, block.css[attrib]) is not None:
                        feature_vec.append(1)
                    # handle binary form
                    elif attrib.encode('utf-8') in block.css \
                        and re.search(token, block.css[attrib.encode('utf-8')].decode('utf-8')) is not None:
                        feature_vec.append(1)
                    else:
                        feature_vec.append(0)

            feature_vec += self.transform_block(block)
            feature_vecs.append(feature_vec)

        return np.stack(feature_vecs, 0).astype(int)
