import requests
from extractnet import Extractor

urls = [
    'https://web.archive.org/web/20221009004120/https://news.gmw.cn/2022-10/08/content_36069304.htm',
    'https://web.archive.org/web/20221009004115/http://ah.anhuinews.com/szxw/202210/t20221008_6438674.html',
    'https://web.archive.org/web/20221009004002/http://www.hljnews.cn/ljxw/content/2022-10/08/content_646280.html',
    'https://web.archive.org/web/20221009004006/https://gddj.southcn.com/node_d601546803/321a3c2343.shtml',
    # 'https://web.archive.org/web/20221009003845/http://www.hljnews.cn/ljxw/content/2022-10/08/content_646277.html'
]


def test_hard_case():
    extractor = Extractor()
    for url in urls:
        web = requests.get(url).content.decode('utf-8')
        result = extractor(web, metadata_mining=True)
        assert '二十大' in result['title']
