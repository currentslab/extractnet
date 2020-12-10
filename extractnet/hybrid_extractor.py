from .extractor import MultiExtractor
from sklearn.base import BaseEstimator
from .metadata_extraction.metadata import extract_metadata

class CascadeExtractor(BaseEstimator):


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
            'headline',
            'description',
            'breadcrumbs'
        ]


        self.author_classifier = author_classifier
        self.date_classifier = date_classifier

        self.author_embedding = joblib.load(author_embeddings)
        self.author_tagger = joblib.load(author_tagger)


    def extract(self, documents, 
            extract_content=True,
            extract_headlines=True,
            encoding=None, 
            as_blocks=False, 
            debug=False, 
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
            if metadata_mining:
                documents_meta_data, meta_ml_fallback = extract_one_meta(documents)
                ml_fallback.update(meta_ml_fallback)
        else:
            documents_meta_data = []
            for document in documents:
                document_meta_data, meta_ml_fallback = extract_one_meta(document)
                ml_fallback.update(meta_ml_fallback)

        ml_results = ml_extract(documents, encoding=encoding, as_blocks=as_blocks, debug=debug, **ml_fallback)
        # we assume the accuracy of meta data is always better than machine learning
        if isinstance(documents, (str, bytes, unicode_, np.unicode_)):
            ml_results.update(documents_meta_data)
            return ml_results 
        else:
            for idx, meta_data in enumerate(documents_meta_data):
                ml_results[idx].update(meta_data)
            return ml_results

    def extract_one_meta(self, document):
        ml_fallback = {}
        meta_data = extract_metadata(documents)
        if 'author' not in meta_data:
            ml_fallback['extract_author'] = True        
        if 'description' not in meta_data:
            ml_fallback['extract_description'] = True
        if 'tags' not in meta_data:
            ml_fallback['extract_breadcrumbs'] = True
        if 'date' not in meta_data:
            ml_fallback['extract_date'] = True
        return meta_data, ml_fallback


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

        target_order = [ (order_idx, MultiExtractor.INVERTED_INDEX[field_idx])  ) \
            for order_idx, field_idx in enumerate(extract_target_index) ]

        return extract_target_index, target_order


    def ml_extract(self, html, encoding=None, as_blocks=False,
            extract_content=True,
            extract_author=True,
            extract_breadcrumbs=True,
            extract_headlines=True,
            extract_description=True,
            extract_date=True,
            ):

        extract_target_index, target_order = self.format_index_feature(
            extract_content=extract_content, 
            extract_headlines=extract_headlines,
            extract_description=extract_description,
            extract_breadcrumbs=extract_breadcrumbs,
        )

        multi_blocks, full_blocks = self.stage1_classifer.extract(html, 
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
            auth_feature = self.stage1_classifer.auth_feat.transform(full_blocks)
            auth_blocks = self.author_classifier.predict_proba(auth_feature)

            if len(full_blocks) > 3:
                best_index = np.argmax(auth_blocks[:, 1])
                auth_prob = auth_blocks[best_index, 1]
                if auth_prob > 0.5:
                    results['rawAuthor'] = str_cast(full_blocks[best_index].text)
                    results['author'] = self.extract_author(results['rawAuthor'])
        if extract_date:
            # reuse if possible
            if auth_feature is None:
                auth_feature = self.stage1_classifer.auth_feat.transform(full_blocks)

            date_blocks = self.date_classifier.predict_proba(auth_feature)
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
