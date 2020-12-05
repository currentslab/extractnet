from extractnet.features.standardized import StandardizedFeature
from extractnet.features.css import CSSFeatures
from extractnet.features.kohlschuetter import KohlschuetterFeatures
from extractnet.features.readability import ReadabilityFeatures
from extractnet.features.weninger import WeningerFeatures, ClusteredWeningerFeatures


def get_feature(name):
    """Get an instance of a ``Features`` class by ``name`` (str)."""
    if name == 'css':
        return CSSFeatures()
    elif name == 'kohlschuetter':
        return KohlschuetterFeatures()
    elif name == 'readability':
        return ReadabilityFeatures()
    elif name == 'weninger':
        return WeningerFeatures()
    elif name == 'clustered_weninger':
        return ClusteredWeningerFeatures()
    else:
        raise ValueError('invalid feature name: "{}"'.format(name))
