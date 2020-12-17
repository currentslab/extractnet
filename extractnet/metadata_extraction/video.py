import datetime
import time
import pytz
from bs4 import BeautifulSoup as bs 
from xml.sax.saxutils import escape
import re
import json
import dateparser
from datetime import datetime
import re

from .utils import parse_server_side_render, parse_ld_json, get_raw_html

YT_EMBED_URL = 'https://www.youtube.com/embed/'

YT_VIDEO = 'https://www.youtube.com/watch?v='
VOX_EMBED_URL = 'https://volume.vox-cdn.com/embed/'

CNBC_EMBED_URL = 'https://player.cnbc.com/p/gZWlPC/cnbc_global?playertype=synd&byGuid='

def handle_akamai_video(akamai_url):
    raw_html = get_raw_html(akamai_url)
    soup = bs(raw_html, 'lxml')
    best_url = None
    best_quality = 0
    if soup.find('video'):
        for video_tag in soup.findAll('video'):
            if video_tag.get('src') and video_tag.get('width'):
                if int(video_tag.get('width')) > best_quality:
                    best_quality = int(video_tag.get('width'))
                    best_url = video_tag.get('src')
    return best_url

def aljazeera_video_prop(vid):
    url = 'https://axis.aljazeera.net/brightcove/cms/media/v1.0/665003303001/videos/{}?format=json&callback=getVideoProperties'.format(vid)
    raw_html = get_raw_html(url)
    if 'getVideoProperties(' in raw_html:
        raw_html = raw_html.replace('getVideoProperties(', '')
        if raw_html[-1] == ')':
            raw_html = raw_html[:-1]
        payload = json.loads(raw_html)
        return payload
    return {}

def speechkit_audio(url):
    raw_html = get_raw_html(url)
    soup = bs(raw_html, 'lxml')
    return soup.find('meta', {'name': 'twitter:player:stream'}).get('content')

def get_advance_fields(raw_html):
    soup = bs(raw_html, 'lxml')

    '''
        Audio extraction
    '''
    audio_tag = soup.find('audio')
    audio_urls = None

    if audio_tag is not None:
        if audio_tag.get('src') and audio_tag.get('type') and audio_tag.get('type') == 'audio/mpeg':
            if audio_urls == None:
                audio_urls = []
            audio_urls.append(audio_tag.get('src'))
        audio_sources = audio_tag.findAll('source')
 
        for audio_source in audio_sources:
            if audio_urls == None:
                audio_urls = []
            audio_urls.append(audio_source.get('src'))

    if soup.find('div', {'class': 'speechkit-container'}):
        speechkit = soup.find('div', {'class': 'speechkit-container'})
        if speechkit.find('iframe'):            
            if audio_urls == None:
                audio_urls = []
            audio_urls.append(speechkit_audio(speechkit.find('iframe').get('src')))

    '''
        Video extraction
    '''

    youtube_iframe = soup.find('iframe', {'id': 'video'})
    video_url = None
    content = None


    if youtube_iframe and youtube_iframe.get('src'):
        youtube_src = youtube_iframe.get('src')
        if youtube_src and YT_EMBED_URL == youtube_src[:len(YT_EMBED_URL)]:
            youtube_id, _ = youtube_src.split('?', 1)
            youtube_id = youtube_id.replace(YT_EMBED_URL, '')
            video_url = 'https://www.youtube.com/watch?v='+youtube_id

    elif soup.find('div', {'data-test': 'VideoPlaceHolder', 'class': 'PlaceHolder-wrapper'}):
        video_id = soup.find('div', {'data-test': 'VideoPlaceHolder', 'class': 'PlaceHolder-wrapper'}).get('data-vilynx-id')
        video_url = CNBC_EMBED_URL+video_id

    elif soup.find('div', { 'class': 'main-article-body'}) and soup.find('div', { 'class': 'main-article-body'}).find('div', {'id': 'vdoContainer'}):
        video_container = soup.find('div', { 'class': 'main-article-body'})
        video_script = video_container.find('script', {'type': 'text/javascript'}).string
        if 'RenderPagesVideo' in video_script:
            video_id, _ = video_script.replace("RenderPagesVideo('", '').split("'", 1)
            props = aljazeera_video_prop(video_id)
            if len(props) > 0:
                rendition = props['renditions'][0]
                video_url = rendition['url']
                content = props['longDescription']

    elif soup.find('div', {'class': 'vxp-media__summary'}):
        content = ''
        for p in soup.find('div', {'class': 'vxp-media__summary'}).findAll('p'):
            content += p.get_text().strip()
        media_player = soup.find('div', {'class': 'media-player-wrapper'})
        figure_data = json.loads(media_player.find('figure').get('data-playable'))
        video_url = figure_data['settings']['externalEmbedUrl']

    elif soup.find('div', {'class': 'c-video-embed volume-video'}):
        video_tag = soup.find('div', {'class': 'c-video-embed volume-video'}).get('data-volume-uuid')
        video_url = VOX_EMBED_URL + video_tag
    elif soup.find('meta', {'property': 'og:video'}) and 'xml' not in soup.find('meta', {'property': 'og:video'}).get('content'):
        video_url = soup.find('meta', {'property': 'og:video'}).get('content')
    elif soup.find('iframe', {'width': True, 'height': True}):
        video_url = soup.find('iframe', {'width': True, 'height': True}).get('src')
    elif soup.find('div', {'id': 'art_video', 'class': 'YTplayer'}):
        video_url = YT_VIDEO+soup.find('div', {'id': 'art_video', 'class': 'YTplayer'}).get('data-ytid')
    elif soup.find('script', {'id': '__NEXT_DATA__', 'type': 'application/json'}):
        payload = soup.find('script', {'id': '__NEXT_DATA__', 'type': 'application/json'}).string
        if 'videoAssets' in payload:
            try:
                payload = json.loads(payload)

                if 'props' in payload and 'initialState' in payload['props']:
                    init_state = payload['props']['initialState']
                    if 'video' in init_state and 'associatedPlaylists' in init_state['video']:
                        video_list = payload['props']['initialState']['video']['associatedPlaylists']
                        if len(video_list) > 0:
                            video = video_list[0]
                            videoAssets = video['videos'][0]
                            asset = videoAssets['videoAssets'][0]
                            if 'publicUrl' in asset:
                                akamai_url = asset['publicUrl']
                                video_url = handle_akamai_video(akamai_url)

            except json.decoder.JSONDecodeError:
                pass
    elif soup.find('video', {'id':'video_player'}) and soup.find('video', {'id':'video_player'}).find('source'):
        video_url = soup.find('video', {'id':'video_player'}).find('source').get('src')

    elif soup.find('video-player', {'video-type': 'youtube'}):
        video_url = soup.find('video-player', {'video-type': 'youtube'}).get('source')

    if video_url != None:
        if YT_EMBED_URL == video_url[:len(YT_EMBED_URL)]:
            if '?' in video_url:
                youtube_id, _ = video_url.split('?', 1)
                youtube_id = youtube_id.replace(YT_EMBED_URL, '')
                video_url = 'https://www.youtube.com/watch?v='+youtube_id
            else:
                youtube_id = video_url.replace(YT_EMBED_URL, '')
                video_url = 'https://www.youtube.com/watch?v='+youtube_id
                
        if '//' == video_url[:2]:
            video_url = 'https:'+video_url

    return {
        'audio': audio_urls,
        'video': video_url,
        'content': content
    }
