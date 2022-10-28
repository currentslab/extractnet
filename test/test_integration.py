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
        res = requests.get(url)
        web = res.content.decode('utf-8')
        result = extractor(web, metadata_mining=True)
        assert '二十大' in result['title']


def test_other_case():
    urls = [
        'https://chechnyatoday.com/news/359220',
        'https://www.msn.com/en-gb/news/newsbirmingham/man-taken-to-hospital-with-burns-after-lithium-battery-explodes-in-great-barr-house/ar-AA12JUmH',
        'http://www.china.org.cn/world/Off_the_Wire/2022-10/08/content_78455811.htm',
        'https://todayisrael.com/2022/10/08/lubricant-and-oil-testing-market-2022-analysis-by-key-players-bureau-veritas-delta-services-industriels-emerson-exxon-mobil-corporation/',
        'https://oil.in-en.com/html/oil-2945141.shtml',
        'https://www.msn.com/zh-tw/money/topstories/%25E5%258F%25B0%25E5%258C%2597%25E6%259C%2580%25E6%2596%25B0%25E6%2588%25BF%25E5%2583%25B9%25E6%258C%2587%25E6%2595%25B8%25E6%259B%259D%25E5%2585%2589-%25E3%2580%258C%25E9%2580%2599%25E7%2594%25A2%25E5%2593%2581%25E3%2580%258D%25E9%2580%25A32%25E6%259C%2588%25E4%25B8%258B%25E6%25BB%2591%25E6%259C%2588%25E7%25B7%259A%25E3%2580%2581%25E5%25AD%25A3%25E7%25B7%259A%25E9%2583%25BD%25E8%25BD%2589%25E6%258A%2598/ar-AA12IMQH',
    ]
    extractor = Extractor()
    for url in urls:
        res = requests.get(url)
        web = res.content.decode('utf-8')
        extractor(web, metadata_mining=True)
