from __future__ import division, print_function

import io
import itertools
import multiprocessing
import os
import re

import ftfy
from lxml import etree
import numpy as np

from extractnet.blocks import Blockifier, simple_tokenizer, text_from_subtree
from extractnet.compat import unicode_
from extractnet.lcs import check_inclusion


RAW_HTML_DIRNAME = 'HTML'
GOLD_STANDARD_DIRNAME = 'Corrected'
GOLD_STANDARD_BLOCKS_DIRNAME = 'block_corrected'

RAW_HTML_EXT = '.html'
GOLD_STANDARD_EXT = '.html.corrected.txt'
GOLD_STANDARD_BLOCKS_EXT = '.block_corrected.txt'

RE_COMMENTS_DELIM = re.compile(r'\n*!@#\$%\^&\*\(\)\s+COMMENTS\n*')

BREAD_CRUMBS_MAX_LENGTH = 150

ignore_breadcrumbs = [
    'Updated on',
    'Posted on',
    'SPONSORED',
    'TRENDING',
    'will be', 
    'includes',
    'for the',
    'are',
    'himself',
    ' in ',
    'In ',
    ' at ',
    ' me ',
    'for',
    'is',
    'Is',
    'kicks off',
    'I am',
    ' with ',
    ' in India',
    'on Facebook',
    'Follow',
    'About Global Ideas',
    'Search by keyword',
    'All rights reserved',
    'is published',
    'soll auch',
    'daran ist',
    'SUBSCRIBE DONATE NEWSLETTERS',
    'Updated',
    'restricciones rebrotes',
    ' receives ',
    ' 2020 Copyright RFI',
    '對啦',
    'The News Lens',
    '資金活水救不了北市店面',
    '位女性的對決',
    '彰化孔子廟隆重登場',
    '硬塞的網路趨勢觀察',
    'ETtoday新聞雲',
    '將是我們',
    '歡迎加入',
    'INSIDE 硬塞的網路趨勢觀察',
    '總覽 議題 政治 國際 中國 社會 財經 環保 司法 專欄 選舉 體育 娛樂 電競 遊戲 旅遊 科技 生活 創夢 美食 新奇 藝文',
    '即時 熱門 政治 社會 生活 國際 地方 蒐奇 影音 財經 娛樂 汽車 時尚 體育 3C 評論 玩咖 食譜 健康 地產 專區',
    '1 2 3 4 5 6 7 8 9 10 11',
]
ignore_breadcrumbs_regex = re.compile('('+'|'.join(ignore_breadcrumbs)+')')

def extract_all_gold_standard_data(data_dir, nprocesses=1,
                                   overwrite=False, **kwargs):
    """
    Extract the gold standard block-level content and comment percentages from a
    directory of labeled data (only those for which the gold standard blocks are
    not found), and save results to corresponding files in a block-level
    gold standard directory under ``data_dir``.

    Args:
        data_dir (str): Directory on disk containing subdirectories for all
            training data, including raw html files and gold standard content +
            comments text files
        nprocesses (int): If > 1, use a :class:`multiprocessing.Pool` to
            parallelize the extractions
        overwrite (bool): If True, overwrite existing gold-standard blocks files.
        **kwargs: passed into :func:`extract_gold_standard_blocks`

    See Also:
        :func:`extract_gold_standard_blocks`
    """
    use_pool = nprocesses > 1
    if use_pool:
        pool = multiprocessing.Pool(processes=nprocesses)

    # get the set of files that have already been block corrected
    # so that we don't block correct them again
    if overwrite is False:
        gs_blocks_dir = os.path.join(data_dir, GOLD_STANDARD_BLOCKS_DIRNAME)
        if not os.path.isdir(gs_blocks_dir):
            os.mkdir(gs_blocks_dir)
        gs_blocks_filenames = get_filenames(
            gs_blocks_dir, full_path=False, match_regex=re.escape(GOLD_STANDARD_BLOCKS_EXT))
        gs_blocks_fileroots = {
            re.search(r'(.+)' + re.escape(GOLD_STANDARD_BLOCKS_EXT), gs_blocks_filename).group(1)
            for gs_blocks_filename in gs_blocks_filenames}
    else:
        gs_blocks_fileroots = set()

    # extract the block-level gold parse from
    # the set of files to be block corrected
    gs_dir = os.path.join(data_dir, GOLD_STANDARD_DIRNAME)
    gs_filenames = get_filenames(
        gs_dir, full_path=False, match_regex=re.escape(GOLD_STANDARD_EXT))
    for i, gs_filename in enumerate(gs_filenames):
        gs_fileroot = re.search(r'(.+)' + re.escape(GOLD_STANDARD_EXT), gs_filename).group(1)
        if gs_fileroot in gs_blocks_fileroots:
            continue
        if i % 100 == 0:
            print('Extracting gold standard blocks for file "{}"'.format(gs_filename))
        if use_pool:
            pool.apply_async(extract_gold_standard_blocks, (data_dir, gs_fileroot), kwargs)
        else:
            extract_gold_standard_blocks(data_dir, gs_fileroot, **kwargs)

    # close out our pool
    if use_pool:
        pool.close()
        pool.join()




def get_filenames(dirname, full_path=False, match_regex=None, extension=None):
    """
    Get all filenames under ``dirname`` that match ``match_regex`` or have file
    extension equal to ``extension``, optionally prepending the full path.

    Args:
        dirname (str): /path/to/dir on disk where files to read are saved
        full_path (bool): if False, return filenames without path; if True,
            return filenames with path, as ``os.path.join(dirname, fname)``
        match_regex (str): include files whose names match this regex pattern
        extension (str): if files only of a certain type are wanted,
            specify the file extension (e.g. ".txt")

    Yields:
        str: next matching filename
    """
    if not os.path.exists(dirname):
        raise OSError('directory "{}" does not exist'.format(dirname))
    match_regex = re.compile(match_regex) if match_regex else None
    for filename in sorted(os.listdir(dirname)):
        if extension and not os.path.splitext(filename)[-1] == extension:
            continue
        if match_regex and not match_regex.search(filename):
            continue
        if full_path is True:
            yield os.path.join(dirname, filename)
        else:
            yield filename


def read_html_file(data_dir, fileroot, encoding=None):
    """
    Read the HTML file corresponding to identifier ``fileroot``
    in the raw HTML directory below the root ``data_dir``.

    Args:
        data_dir (str)
        fileroot (str)
        encoding (str)

    Returns:
        str
    """
    fname = os.path.join(
        data_dir, RAW_HTML_DIRNAME, fileroot + RAW_HTML_EXT)
    encodings = (encoding,) if encoding else ('utf-8', 'iso-8859-1')  # 'utf-16'
    for encoding in encodings:
        try:
            with io.open(fname, mode='rt', encoding=encoding) as f:
                raw_html = f.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            raw_html = None

    return ftfy.fix_encoding(raw_html).strip()


def read_gold_standard_file(data_dir, fileroot, encoding=None, cetr=False):
    """
    Read the gold standard content file corresponding to identifier ``fileroot``
    in the gold standard directory below the root ``data_dir``.

    Args:
        data_dir (str)
        fileroot (str)
        encoding (str)
        cetr (bool): if True, assume no comments and parse the gold standard
            to remove tags

    Returns:
        List[str, str]: contents string and comments string, respectively
    """
    fname = os.path.join(
        data_dir, GOLD_STANDARD_DIRNAME, fileroot + GOLD_STANDARD_EXT)
    encodings = (encoding,) if encoding else ('utf-8', 'utf-16', 'iso-8859-1')
    for encoding in encodings:
        try:
            with io.open(fname, mode='rt', encoding=encoding) as f:
                gold_standard = f.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            gold_standard = None

    if not gold_standard:
        return [u'', u'']

    if not cetr:
        content_comments = RE_COMMENTS_DELIM.split(gold_standard, maxsplit=1)
        # if no comments delimiter found, append empty comments string
        if len(content_comments) == 1:
            content_comments = [content_comments[0], u'']
    else:
        tree = etree.fromstring(gold_standard, parser=etree.HTMLParser())
        content_comments = [u' '.join(text_from_subtree(tree)), u'']

    # fix text in case of mangled encodings
    content_comments = [ftfy.fix_encoding(content_comments[0]).strip(),
                        ftfy.fix_encoding(content_comments[1]).strip()]

    return content_comments


def read_gold_standard_blocks_file(data_dir, fileroot, split_blocks=True):
    """
    Read the gold standard blocks file corresponding to identifier ``fileroot``
    in the gold standard blocks directory below the root ``data_dir``.

    Args:
        data_dir (str)
        fileroot (str)
        split_blocks (bool): If True, split the file's content into blocks.

    Returns:
        str or List[str]
    """
    fname = os.path.join(
        data_dir, GOLD_STANDARD_BLOCKS_DIRNAME, fileroot + GOLD_STANDARD_BLOCKS_EXT)
    with io.open(fname, mode='r') as f:
        data = f.read()
    if split_blocks:
        return filter(None, data[:-1].split('\n'))
    return filter(None, data)


def _parse_target_blocks(blocks, block_pct_tokens_thresh, is_bread_crumb=False):
    if not is_bread_crumb:
        is_above_thresh = (np.array([ele[0] for ele in blocks]) > block_pct_tokens_thresh).astype(np.int)
    else:
        with open('parse_breadcrumbs.txt', 'a') as f:
            for ele in blocks:
                if ele[0] > block_pct_tokens_thresh and ignore_breadcrumbs_regex.search(' '.join(ele[2])) == None:
                    f.write(' '.join(ele[2])+'\n')
        is_above_thresh = [1 if (
            # is above threshold
            ele[0] > block_pct_tokens_thresh and \
            # is longer than 2 and smaller than BREAD_CRUMBS_MAX_LENGTH
            len(' '.join(ele[2])) >= 2 and \
            len(' '.join(ele[2])) < BREAD_CRUMBS_MAX_LENGTH and \
            # not in ignore words
            ignore_breadcrumbs_regex.search(' '.join(ele[2])) == None ) else 0 for ele in blocks  ]
        is_above_thresh = np.array(is_above_thresh).astype(np.int)

    token_counts = np.array([ele[1] for ele in blocks])
    all_tokens = list(itertools.chain.from_iterable(
        ele[2] for ele in blocks if ele[1] > 0))

    return (is_above_thresh, token_counts, all_tokens)


def prepare_data(params):
    data_dir, fileroot, block_pct_tokens_thresh = params
    """
    Prepare data for a single HTML + gold standard blocks example, uniquely
    identified by ``fileroot``.

    Args:
        data_dir (str)
        fileroot (str)
        block_pct_tokens_thresh (float): must be in [0.0, 1.0]

    Returns:
        Tuple[str, Tuple[np.array[int], np.array[int], List[str]], Tuple[np.array[int], np.array[int], List[str]]]:
            The first element is simply the raw html as a string. The second and
            third elements are 3-tuples for content and comments, respectively,
            where the first element is a numpy array of 1s and 0s whose values
            correspond to whether or not a given block is considered non-content
            or not; the second element is a numpy integer array whose values are
            the total number of tokens in each block; and the third element is
            a flat list of content or comment tokens as strings, concatenated
            from all blocks.

    See Also:
        :func:`prepare_all_data`
    """
    if isinstance(block_pct_tokens_thresh, float):
        if not 0.0 <= block_pct_tokens_thresh <= 1.0:
            raise ValueError('block_pct_tokens_thresh must be in the range [0.0, 1.0]')
        block_pct_tokens_thresh = [block_pct_tokens_thresh]*6
    else:
        assert isinstance(block_pct_tokens_thresh, list)
        assert len(block_pct_tokens_thresh) == 6

    html = read_html_file(data_dir, fileroot)
    blocks = read_gold_standard_blocks_file(data_dir, fileroot, split_blocks=True)

    content_blocks = []
    headline_blocks = []
    datepub_blocks = []
    author_blocks = []
    desc_blocks = []
    bread_blocks = []

    for block in blocks:
        #      0               1                2           3           4       
        #  {frac_content}\t{frac_author}\t{frac_desc}\t{frac_head}\t{frac_bread}\t
        #         5                6              7                 8       
        # {frac_datepub}\t{frac_datemod}\t{block_tokens}\t{content_tokens}\t
        #          9               10          11              12              13              14
        # {author_tokens}\t{desc_tokens}\t{head_tokens}\t{bread_tokens}\t{datepub_tokens}\t{datemod_tokens}\n'
        block_split = block.split('\t')
        num_block_tokens = len(block_split[6].split())
        # total number of tokens in block is used as weights
        content_blocks.append(
            (float(block_split[0]), num_block_tokens, block_split[7].split()))
        author_blocks.append(
            (float(block_split[1]), num_block_tokens, block_split[8].split()))
        desc_blocks.append(
            (float(block_split[2]), num_block_tokens, block_split[9].split()))    
        headline_blocks.append(
            (float(block_split[3]), num_block_tokens, block_split[10].split()))
        bread_blocks.append(
            (float(block_split[4]), num_block_tokens, block_split[11].split()))
        datepub_blocks.append(
            (float(block_split[5]), num_block_tokens, block_split[12].split()))

    parsed_content_blocks = _parse_target_blocks( content_blocks, block_pct_tokens_thresh[0])
    parsed_author_blocks = _parse_target_blocks( author_blocks, block_pct_tokens_thresh[1])
    parsed_desc_blocks = _parse_target_blocks( desc_blocks, block_pct_tokens_thresh[2])
    parsed_headline_blocks = _parse_target_blocks( headline_blocks, block_pct_tokens_thresh[3])
    parsed_bread_blocks = _parse_target_blocks( bread_blocks, block_pct_tokens_thresh[4], is_bread_crumb=True)
    parsed_datepub_blocks = _parse_target_blocks( datepub_blocks, block_pct_tokens_thresh[5])


    return (html, parsed_content_blocks, parsed_author_blocks, \
        parsed_desc_blocks, parsed_headline_blocks, parsed_bread_blocks, parsed_datepub_blocks
        )


def prepare_all_data(data_dir, block_pct_tokens_thresh=0.1, extract_top=-1):
    from multiprocessing import Pool
    from tqdm import tqdm

    """
    Prepare data for all HTML + gold standard blocks examples in ``data_dir``.

    Args:
        data_dir (str)
        block_pct_tokens_thresh (float): must be in [0.0, 1.0]

    Returns:
        List[Tuple[str, List[float, int, List[str]], List[float, int, List[str]]]]

    See Also:
        :func:`prepare_data`
    """
    gs_blocks_dir = os.path.join(data_dir, GOLD_STANDARD_BLOCKS_DIRNAME)
    gs_blocks_filenames = get_filenames(
        gs_blocks_dir, full_path=False, match_regex=re.escape(GOLD_STANDARD_BLOCKS_EXT))

    gs_blocks_fileroots = (
        re.search(r'(.+)' + re.escape(GOLD_STANDARD_BLOCKS_EXT), gs_blocks_filename).group(1)
        for gs_blocks_filename in gs_blocks_filenames)

    pool = Pool()
    params = [  (data_dir, fileroot, block_pct_tokens_thresh, )  for fileroot in gs_blocks_fileroots ]
    if extract_top > 1:
        return [results for results in tqdm(pool.imap(prepare_data,params[:extract_top])) ]

    return [results for results in tqdm(pool.imap(prepare_data,params)) ]
