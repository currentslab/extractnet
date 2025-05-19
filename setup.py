#!/usr/bin/env python

# Copyright (c) 2012 SEOmoz
# Copyright (c) 2020 Pheme Pte Ltd
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os.path
import platform
from setuptools import setup
# have to import `Extension` after `setuptools.setup`
from distutils.extension import Extension
import sys
import re, io
from Cython.Distutils import build_ext
from Cython.Build import cythonize
import lxml
from numpy import get_include

def find_libxml2_include():
    include_dirs = []
    for d in ['/usr/include/libxml2', '/usr/local/include/libxml2']:
        if os.path.exists(os.path.join(d, 'libxml/tree.h')):
            include_dirs.append(d)
    return include_dirs

# set min MacOS version, if necessary
if sys.platform == 'darwin':
    os_version = '.'.join(platform.mac_ver()[0].split('.')[:2])
    # this seems to work better than the -mmacosx-version-min flag
    os.environ['MACOSX_DEPLOYMENT_TARGET'] = os_version

ext_modules = [
    Extension('extractnet.lcs',
              sources=["extractnet/lcs.pyx"],
              include_dirs=[get_include()],
              language="c++"),
    Extension('extractnet.blocks',
              sources=["extractnet/blocks.pyx"],
              include_dirs=(lxml.get_include() + find_libxml2_include()),
              language="c++",
              libraries=['xml2']),
    Extension('extractnet.features._readability',
              sources=["extractnet/features/_readability.pyx"],
              include_dirs=[get_include()],
              extra_compile_args=['-std=c++11'],
              language="c++"),
    Extension('extractnet.features._kohlschuetter',
              sources=["extractnet/features/_kohlschuetter.pyx"],
              include_dirs=[get_include()],
              language="c++"),
    Extension('extractnet.features._weninger',
              sources=["extractnet/features/_weninger.pyx"],
              include_dirs=[get_include()],
              language="c++"),
]

this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

__version__ = re.search(
    r'__version__\s*=\s*[\'"]([^\'"]*)[\'"]',  # It excludes inline comment too
    io.open('extractnet/__init__.py', encoding='utf_8_sig').read()
    ).group(1)

setup(
    name='extractnet',
    version=__version__,
    description='Extract the main article content (and optionally comments) from a web page',
    author='Peter',
    author_email='sales@currentsapi.services',
    url='https://github.com/currentsapi/extractnet',
    license='MIT',
    platforms='Posix; MacOS X',
    keywords='automatic content extraction, web page dechroming, HTML parsing',
    long_description=long_description,
    long_description_content_type='text/markdown',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Scientific/Engineering',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'Intended Audience :: Science/Research',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    packages=[
        'extractnet', 'extractnet.features', 
        'extractnet.metadata_extraction', 
        'extractnet.sequence_tagger',
        'extractnet.features'
        ],
    package_dir={
        'extractnet': 'extractnet', 
        'extractnet.metadata_extraction': 'extractnet/metadata_extraction',
        'extractnet.features': 'extractnet/features',
        'extractnet.sequence_tagger': 'extractnet/sequence_tagger' },
    package_data={'extractnet': ['pickled_models/*/*', 'models/*', '*', 'features/*']},
    cmdclass={'build_ext': build_ext},
    ext_modules=cythonize(ext_modules),
    setup_requires = [
        'lxml',
        'numpy',
        'Cython>=0.21.1',
    ],
    install_requires=[
        'cchardet>=2.1.7',
        'beautifulsoup4==4.9.3',
        'ftfy>=4.1.0,<5.0.0',
        'numpy>=1.19.0',
        'onnxruntime>=1.9.0',
        'scikit-learn>=0.22.0',
        'tld==0.12.6',
        'scipy>=0.17.0',
        'sklearn-crfsuite==0.3.6',
        'dateparser>=1.1.0',
        'joblib>=1.1.0',
        'htmldate==0.7.2'
    ]
)
