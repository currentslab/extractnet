import onnxruntime as ort
import numpy as np
from scipy.special import expit
from sklearn.utils.extmath import softmax
from .compat import str_cast
from .util import get_and_union_features, get_module_res, fix_encoding
from .blocks import TagCountReadabilityBlockifier



class NewsNet():
    '''
        Inputs 
    '''
    # order must be fixed
    label_order = ('content', 'author', 'headline', 'breadcrumbs', 'date')

    BASE_FEAT_SIZE = 9

    CSS_FEAT_SIZE = 43
    feats = ('kohlschuetter', 'weninger', 'readability', 'css')

    def __init__(self, model_weight=None, cls_threshold=0.1, binary_threshold=0.5):
        self.feature_transform = get_and_union_features(self.feats)
        model_weight = get_module_res('models/news_net.onnx') if model_weight is None else model_weight
        self.ort_session = ort.InferenceSession(model_weight)
        self.binary_threshold = binary_threshold
        self.cls_threshold = cls_threshold


    def preprocess(self, html):
        blocks = TagCountReadabilityBlockifier.blockify(html, encoding='utf-8')
        blocks = np.array(blocks)
        feat = self.feature_transform.transform(blocks).astype(np.float32)
        return feat, blocks


    def predict(self, html):
        single = False
        if isinstance(html, list):
            x, css, blocks= [], [], []
            for html_ in html:
                feat, block = self.preprocess(html_)
                x.append(feat[:, :self.BASE_FEAT_SIZE])
                css.append(feat[:, self.BASE_FEAT_SIZE:])
                blocks.append(block)
            x = np.array(x)
            css = np.array(css)
        else:
            single = True
            feat, block = self.preprocess(html)
            x = np.array([feat[:, :self.BASE_FEAT_SIZE]])
            css = np.array([feat[:, self.BASE_FEAT_SIZE:]])
            blocks = [block]

        inputs_onnx = { 'input': x, 'css': css }

        logits = self.ort_session.run(None, inputs_onnx)[0]
        decoded = self.decode_output(logits, blocks)
        return decoded[0] if single else decoded

    def decode_output(self, logits, doc_blocks):
        outputs = []
        for jdx, preds in enumerate(logits):
            output = {}
            blocks = doc_blocks[jdx]
            for idx, label in enumerate(self.label_order):
                if label in ['author', 'date', 'breadcrumbs']:
                    top_k = 10
                    scores = softmax([preds[:, idx]])[0]
                    ind = np.argpartition(preds[:, idx], -top_k)[-top_k:]
                    result = [ (fix_encoding(str_cast(blocks[idx].text)), scores[idx]) for idx in ind if scores[idx] > self.cls_threshold]
                    # sort values by confidence
                    output[label] = sorted(result, key=lambda x:x[1], reverse=True)
                else:
                    mask = expit(preds[:, idx]) > self.binary_threshold
                    ctx = fix_encoding(str_cast(b'\n'.join([ b.text for b in blocks[mask]])))
                    if len(ctx) == 0:
                        ctx = None
                    output[label] = ctx
            outputs.append(output)
        return outputs

