import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import random
import time

class Hanime1API:
    def __init__(self):
        self.base_url = "https://hanime1.me"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'Referer': f'{self.base_url}/',
            'Origin': self.base_url,
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.session.trust_env = False
        self.session.verify = True
        
        self.proxy_config = {
            'http': 'https://mrwdfNTD8M79LCukCieldrqZWqs=:exaxgqkKkd0TAMrCxeonWg==@tw4-cdn-route.couldflare-cdn.com:443',
            'https': 'https://mrwdfNTD8M79LCukCieldrqZWqs=:exaxgqkKkd0TAMrCxeonWg==@tw4-cdn-route.couldflare-cdn.com:443'
        }
        
        self.proxy_enabled = False
        self.session.proxies = {}
    
    def enable_proxy(self):
        try:
            self.session.proxies = {
                'http': 'https://mrwdfNTD8M79LCukCieldrqZWqs=:exaxgqkKkd0TAMrCxeonWg==@tw4-cdn-route.couldflare-cdn.com:443',
                'https': 'https://mrwdfNTD8M79LCukCieldrqZWqs=:exaxgqkKkd0TAMrCxeonWg==@tw4-cdn-route.couldflare-cdn.com:443'
            }
            self.proxy_enabled = True
        except Exception:
            pass
    
    def disable_proxy(self):
        try:
            self.session.proxies.clear()
            self.proxy_enabled = False
        except Exception:
            pass
    
    def is_proxy_enabled(self):
        return self.proxy_enabled
    
    def search_videos(self, query, genre="", sort="", date="", duration="", page=1):
        params = {
            'query': query,
            'type': '',
            'genre': genre,
            'sort': sort,
            'date': date,
            'duration': duration,
            'page': page if page > 1 else None
        }
        params = {k: v for k, v in params.items() if v}
        
        try:
            url = f"{self.base_url}/search"
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                return None
            
            html_content = None
            content_encoding = response.headers.get('Content-Encoding', '').lower()
            try:
                if 'br' in content_encoding:
                    import brotli
                    html_content = brotli.decompress(response.content).decode('utf-8')
                else:
                    response.encoding = 'utf-8'
                    html_content = response.text
            except Exception:
                try:
                    html_content = response.text
                except:
                    return None
            
            if not html_content or '<html' not in html_content.lower() and '<!doctype' not in html_content.lower():
                return None
            
            soup = BeautifulSoup(html_content, 'html.parser')
            search_info = {
                'query': query,
                'params': params,
                'total_results': 0,
                'current_page': page,
                'total_pages': 1,
                'videos': [],
                'has_results': False
            }
            
            video_items = soup.find_all('div', class_='search-doujin-videos')
            for item in video_items:
                video_link = item.find('a', class_='overlay')
                if video_link and hasattr(video_link, 'attrs') and 'href' in video_link.attrs:
                    match = re.search(r'v=(\d+)', video_link['href'])
                    if match:
                        video_id = match.group(1)
                        if any(v['video_id'] == video_id for v in search_info['videos']):
                            continue
                        title = item.get('title', f"视频 {video_id}")
                        img_tags = item.find_all('img')
                        thumbnail = ""
                        for img in img_tags:
                            if img.get('src'):
                                if 'thumbnail' in img.get('src'):
                                    thumbnail = img.get('src')
                                    break
                        if not thumbnail and img_tags:
                            for img in img_tags:
                                if img.get('src'):
                                    thumbnail = img.get('src')
                                    break
                        search_info['videos'].append({
                            'video_id': video_id,
                            'title': title,
                            'url': f"{self.base_url}/watch?v={video_id}",
                            'thumbnail': thumbnail
                        })
            
            if not search_info['videos']:
                all_links = soup.find_all('a', href=re.compile(r'/watch\?v=\d+'))
                for link in all_links:
                    match = re.search(r'v=(\d+)', link['href'])
                    if match:
                        video_id = match.group(1)
                        if not any(v['video_id'] == video_id for v in search_info['videos']):
                            title_elem = link.find(class_=re.compile(r'.*title.*|.*name.*'))
                            title = title_elem.get_text(strip=True) if title_elem else f"视频 {video_id}"
                            img = link.find('img')
                            thumbnail = img.get('src') if img else ''
                            search_info['videos'].append({
                                'video_id': video_id,
                                'title': title,
                                'url': f"{self.base_url}/watch?v={video_id}",
                                'thumbnail': thumbnail
                            })
            
            pagination = soup.find('div', class_='search-pagination')
            if pagination:
                page_links = pagination.find_all('a', href=re.compile(r'.*page=\d+.*'))
                if page_links:
                    page_numbers = []
                    for link in page_links:
                        text = link.get_text(strip=True)
                        if text.isdigit():
                            page_numbers.append(int(text))
                    if page_numbers:
                        search_info['total_pages'] = max(page_numbers)
            
            skip_form = soup.find('form', {'id': 'skip-page-form'})
            if skip_form:
                total_div = skip_form.find('div', string=re.compile(r'/\s*\d+'))
                if total_div:
                    match = re.search(r'/(d+)', total_div.get_text())
                    if match:
                        search_info['total_pages'] = int(match.group(1))
            
            search_info['total_results'] = len(search_info['videos'])
            search_info['has_results'] = len(search_info['videos']) > 0
            return search_info
            
        except requests.RequestException:
            return None
        except Exception:
            return None
    
    def get_video_info(self, video_id):
        url = f"{self.base_url}/watch?v={video_id}"
        max_retries = 3
        for retry in range(max_retries):
            try:
                video_headers = self.headers.copy()
                chrome_versions = ['120.0.0.0', '119.0.0.0', '118.0.0.0']
                chrome_version = random.choice(chrome_versions)
                video_headers.update({
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Referer': f'{self.base_url}/search?query=test',
                })
                
                home_response = self.session.get(self.base_url, headers=video_headers, timeout=10)
                delay = random.uniform(0.5, 1.5)
                time.sleep(delay)
                response = self.session.get(url, headers=video_headers, timeout=15)
                
                if response.status_code != 200:
                    if response.status_code == 403:
                        self.session.cookies.clear()
                        time.sleep(random.uniform(1, 2))
                        continue
                    return None
                
                html_content = None
                content_encoding = response.headers.get('Content-Encoding', '').lower()
                try:
                    if 'br' in content_encoding:
                        import brotli
                        html_content = brotli.decompress(response.content).decode('utf-8')
                    elif 'gzip' in content_encoding:
                        import gzip
                        try:
                            if response.content.startswith(b'\x1f\x8b'):
                                html_content = gzip.decompress(response.content).decode('utf-8')
                            else:
                                response.encoding = 'utf-8'
                                html_content = response.text
                        except (gzip.BadGzipFile, OSError, EOFError):
                            response.encoding = 'utf-8'
                            html_content = response.text
                    elif 'deflate' in content_encoding:
                        import zlib
                        try:
                            html_content = zlib.decompress(response.content).decode('utf-8')
                        except Exception:
                            response.encoding = 'utf-8'
                            html_content = response.text
                    else:
                        response.encoding = 'utf-8'
                        html_content = response.text
                except Exception:
                    html_content = response.text
                
                if not html_content or '<html' not in html_content.lower():
                    continue
                
                try:
                    soup = BeautifulSoup(html_content, 'lxml')
                except:
                    soup = BeautifulSoup(html_content, 'html.parser')
                
                video_info = {
                    'video_id': video_id,
                    'url': url,
                    'title': '',
                    'chinese_title': '',
                    'description': '',
                    'views': '',
                    'upload_date': '',
                    'likes': '',
                    'video_sources': [],
                    'tags': [],
                    'series': [],
                    'thumbnail': ''
                }
                
                title_tag = soup.find('title')
                if title_tag:
                    full_title = title_tag.get_text(strip=True)
                    if ' - Hanime1' in full_title:
                        video_info['title'] = full_title.split(' - Hanime1')[0].strip()
                    elif ' - H動漫' in full_title:
                        video_info['title'] = full_title.split(' - H動漫')[0].strip()
                    else:
                        video_info['title'] = full_title
                
                h3_title = soup.find('h3', {'id': 'shareBtn-title'})
                if h3_title:
                    video_info['chinese_title'] = h3_title.get_text(strip=True)
                
                view_info = soup.find('div', class_='video-description-panel')
                if view_info:
                    panel_text = view_info.get_text(strip=True)
                    view_match = re.search(r'观看次数：([\d.]+万次)', panel_text)
                    if view_match:
                        video_info['views'] = view_match.group(1)
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', panel_text)
                    if date_match:
                        video_info['upload_date'] = date_match.group(1)
                
                like_button = soup.find('button', {'id': 'video-like-btn'})
                if like_button:
                    like_text = like_button.get_text(strip=True)
                    match = re.search(r'(\d+%)\s*\((\d+)\)', like_text)
                    if match:
                        video_info['likes'] = f"{match.group(1)} ({match.group(2)}票)"
                
                video_tag = soup.find('video', {'id': 'player'})
                if video_tag:
                    poster = video_tag.get('poster')
                    if poster:
                        video_info['thumbnail'] = poster
                    sources = video_tag.find_all('source')
                    for source in sources:
                        src = source.get('src')
                        if src:
                            if not src.startswith('http'):
                                src = urljoin(self.base_url, src)
                            video_info['video_sources'].append({
                                'url': src,
                                'quality': source.get('size', 'unknown'),
                                'type': source.get('type', 'video/mp4')
                            })
                
                if not video_info['video_sources']:
                    script_tags = soup.find_all('script')
                    for script in script_tags:
                        script_content = script.string or ''
                        if script_content:
                            if any(keyword in script_content for keyword in ['videoUrl', 'videoSrc', 'sourceUrl', 'mp4', 'playerConfig', 'videoConfig']):
                                video_url_patterns = [
                                    r'https?://[^"\'\s<>]+\.(?:mp4|m3u8|webm|flv)',
                                    r'(?:videoUrl|videoSrc|sourceUrl|file)\s*[:=]\s*["\']([^"\']+)["\']',
                                    r'["\'](https?://[^"\']+\.(?:mp4|m3u8|webm))["\']',
                                    r'<source[^>]+src=["\']([^"\']+)["\']'
                                ]
                                for pattern in video_url_patterns:
                                    matches = re.findall(pattern, script_content, re.IGNORECASE)
                                    if matches:
                                        for match in matches:
                                            video_url = match[0] if isinstance(match, tuple) else match
                                            if not video_url.startswith('http'):
                                                continue
                                            if not any(ext in video_url.lower() for ext in ['.mp4', '.m3u8', '.webm', '.flv']):
                                                continue
                                            if not any(source['url'] == video_url for source in video_info['video_sources']):
                                                video_info['video_sources'].append({
                                                    'url': video_url,
                                                    'quality': 'unknown',
                                                    'type': 'video/mp4'
                                                })
                                if video_info['video_sources']:
                                    break
                
                if not video_info['video_sources']:
                    video_url_pattern = r'(https?://[^"\'\s<>]+\.(?:mp4|m3u8|webm|flv))'
                    matches = re.findall(video_url_pattern, html_content)
                    if matches:
                        for video_url in matches:
                            if not any(source['url'] == video_url for source in video_info['video_sources']):
                                video_info['video_sources'].append({
                                    'url': video_url,
                                    'quality': 'unknown',
                                    'type': 'video/mp4'
                                })
                
                tags_div = soup.find('div', class_='video-tags-wrapper')
                if tags_div:
                    tag_links = tags_div.find_all('a')
                    for link in tag_links:
                        tag_text = link.get_text(strip=True)
                        if tag_text and tag_text != '#' and 'http' not in tag_text:
                            video_info['tags'].append(tag_text)
                
                description_div = soup.find('div', class_='video-caption-text')
                if description_div:
                    video_info['description'] = description_div.get_text(strip=True)
                
                playlist_items = soup.find_all('div', class_='related-watch-wrap')
                series_info = []
                for item in playlist_items:
                    link = item.find('a', class_='overlay')
                    if link and link.get('href'):
                        video_url = link.get('href')
                        match = re.search(r'v=(\d+)', video_url)
                        if match:
                            vid = match.group(1)
                            title = item.get('title', '')
                            chinese_title = title
                            title_elem = item.find('div', class_=re.compile(r'.*title.*|.*name.*'))
                            if title_elem:
                                title_text = title_elem.get_text(strip=True)
                                if title_text:
                                    chinese_title = title_text
                            img_tag = item.find('img')
                            thumbnail = img_tag.get('src') if img_tag and img_tag.get('src') else ''
                            duration_div = item.find('div', class_='card-mobile-duration')
                            duration = duration_div.get_text(strip=True) if duration_div else ''
                            series_info.append({
                                'video_id': vid,
                                'title': title,
                                'chinese_title': chinese_title,
                                'url': f"{self.base_url}/watch?v={vid}",
                                'thumbnail': thumbnail,
                                'duration': duration
                            })
                
                seen = set()
                unique_series = []
                for item in series_info:
                    if item['video_id'] not in seen:
                        seen.add(item['video_id'])
                        unique_series.append(item)
                video_info['series'] = unique_series
                return video_info
                
            except requests.RequestException:
                if retry < max_retries - 1:
                    time.sleep(random.uniform(1, 2))
                    continue
                return None
            except Exception:
                if retry < max_retries - 1:
                    time.sleep(random.uniform(1, 2))
                    continue
                return None
