'''

    Test on real world websites

'''
import requests
from extractnet import extract_news

def test_wiki_page():
    example_urls = [
        'https://en.wikipedia.org/wiki/Shyster_(expert_system)',
        'https://en.wikipedia.org/wiki/Pareto_front',
        'https://zh.wikipedia.org/wiki/%E8%A5%BF%E8%A5%BF%E9%87%8C%E5%B2%9B'
    ]


    for url in example_urls:
        res = requests.get(url)
        html_text = res.text
        result = extract_news(html_text)
        assert 'title' in result
        # non empty title
        assert len(result['title']) > 0
        assert 'content' in result
        # non empty content
        assert len(result['content']) > 30
