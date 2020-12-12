import joblib
import json
import re
import numpy as np

NON_WORD_CHAR = re.compile(r'[-|——|,|.|:|@|#|!|$|%|^|&|*|，|、|；|-|+|~|`|⋯⋯|。| |  |/|｜|】|【|」| 》|>|<|《|;|；|：|」|"|\'|／|「]')

def word2features(sent, i, embeddings):
    word = sent[i]

    features = {
        'bias': 1.0,
        'word.lower()': word.lower(),
        'word.isupper()': word.isupper(),
        'word.istitle()': word.istitle(),
        'trigram': ''.join(sent[ i-1:i+2 ]).lower(),
        'bigram': ''.join(sent[ i-1:i+1 ]).lower(),
        'tribigram': ''.join(sent[ i:i+3 ]).lower(),
        'pentagram': ''.join(sent[ i:i+5 ]).lower(),
        'word.isspace()': word.isspace(),
        'word.issymbol()': NON_WORD_CHAR.match(word) is None,
        'word.isdigit()': word.isdigit(),
        'position_idx': i
    }

    if word not in embeddings:
        embedding = embeddings['UNK']
    else:
        embedding = embeddings[word]

    for idx, val in enumerate(embedding):
        features[str(idx)+'_embed'] = val

    if i > 0:
        word1 = sent[i-1][0]
        features.update({
            '-1:word.lower()': word1.lower(),
            '-1:word.istitle()': word1.istitle(),
            '-1:word.isupper()': word1.isupper(),
        })
    else:
        features['BOS'] = True

    if i < len(sent)-1:
        word1 = sent[i+1][0]
        features.update({
            '+1:word.lower()': word1.lower(),
            '+1:word.istitle()': word1.istitle(),
            '+1:word.isupper()': word1.isupper(),
        })
    else:
        features['EOS'] = True

    return features

class NameExtractor():

    def __init__(self, embedding, crf_model):
        if isinstance(embedding, str):
            embedding = joblib.load(embedding)

        if isinstance(crf_model, str):
            crf_model = joblib.load(crf_model)

        self.embedding = embedding
        self.crf_model = crf_model
    
    def preprocess(self, sent):
        return [  word2features(sent, i, self.embedding) for i in range(len(sent)) ]

    def extract_token(self, pred_label, text):
        names = []
        name = ''
        for idx, char in enumerate(text):
            if pred_label[idx] == 'B':
                if len(name) > 0:
                    names.append(name)
                    name = ''
                name += char
            elif pred_label[idx] == 'I':
                name += char
            else: # O
                if len(name) > 0:
                    names.append(name)
                    name = ''
        if len(name) > 0:
            names.append(name)
        return names



    def predict(self, sent):
        if isinstance(sent, str):
            feature = self.preprocess(sent)
            feature = [feature]
            text = [sent]
        elif isinstance(sent, list):
            feature = [ self.preprocess(s) for s in sent ]
            text = sent

        y_preds = []

        for y_margin in self.crf_model.predict_marginals(feature):
            y_pred = []
            for output in y_margin:
                label_right = max(output, key=output.get)
                y_pred.append(label_right)
            y_preds.append(y_pred)

        if isinstance(sent, str):
            return self.extract_token(y_preds[0], sent)
        return [ self.extract_token(pred, text[idx])  for idx, pred in enumerate(y_preds) ]


if __name__ == '__main__':
    print('start')
    extractor = NameExtractor('extractnet/models/char_embedding.joblib', 'extractnet/models/crf.joblib')
    for idx in range(5):
        print(word2features('文／記者劉讖語', idx, extractor.embedding))

    # print(extractor.predict('文／記者劉讖語'))
    # print(extractor.predict('By Sarah Mervosh and Lucy Tompkins'))
    # print(extractor.predict('By Sarah Mervosh'))