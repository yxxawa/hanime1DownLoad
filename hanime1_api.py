import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import quote, urlencode, urljoin
import time
import os
import glob
import pickle


def cleanup_old_html_files():
    search_files = glob.glob('search_response_*.html')
    video_files = glob.glob('video_response_*.html')
    all_files = search_files + video_files
    for file in all_files:
        try:
            os.remove(file)
        except Exception:
            pass

cleanup_old_html_files()

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
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'Referer': f'{self.base_url}/',
            'Origin': self.base_url,
            'DNT': '1',
            'Sec-GPC': '1',
            'TE': 'trailers',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"10.0.0"',
            'sec-ch-ua-arch': '"x86"',
            'sec-ch-ua-bitness': '"64"',
            'sec-ch-ua-full-version': '"120.0.6099.217"',
            'sec-ch-ua-full-version-list': '"Google Chrome";v="120.0.6099.217", "Chromium";v="120.0.6099.217", "Not_A Brand";v="24.0.0.0"',
            'sec-ch-ua-wow64': '?0',
            'X-Requested-With': 'XMLHttpRequest',
            'X-Real-IP': '127.0.0.1',
            'X-Forwarded-For': '127.0.0.1',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.session.trust_env = False
        self.session.verify = True
        self.session.headers.update({
            'X-Forwarded-For': '',
            'Via': '',
            'Proxy-Connection': '',
        })
        self.proxy_config = {
            'http': 'https://mrwdfNTD8M79LCukCieldrqZWqs=:exaxgqkKkd0TAMrCxeonWg==@tw4-cdn-route.couldflare-cdn.com:443',
            'https': 'https://mrwdfNTD8M79LCukCieldrqZWqs=:exaxgqkKkd0TAMrCxeonWg==@tw4-cdn-route.couldflare-cdn.com:443'
        }
        self.proxy_enabled = False
        self.session.proxies = {}
        self.session.cookies.set('cf_clearance', '')
        
        # 缓存相关属性
        self.cache_dir = "cache"
        self.search_cache_file = os.path.join(self.cache_dir, "search_cache.pkl")
        self.video_cache_file = os.path.join(self.cache_dir, "video_cache.pkl")
        self.cache_expiry = 48 * 60 * 60  # 缓存过期时间，48小时
        
        # 初始化缓存
        self._init_cache()
        
    def _init_cache(self):
        """
        初始化缓存，确保缓存目录和文件存在
        """
        # 创建缓存目录
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        
        # 加载搜索缓存
        try:
            with open(self.search_cache_file, 'rb') as f:
                self.search_cache = pickle.load(f)
        except (FileNotFoundError, pickle.UnpicklingError, EOFError):
            self.search_cache = {}
        
        # 加载视频缓存
        try:
            with open(self.video_cache_file, 'rb') as f:
                self.video_cache = pickle.load(f)
        except (FileNotFoundError, pickle.UnpicklingError, EOFError):
            self.video_cache = {}
    
    def _save_cache(self):
        """
        保存缓存到文件
        """
        try:
            with open(self.search_cache_file, 'wb') as f:
                pickle.dump(self.search_cache, f)
        except Exception:
            pass
        
        try:
            with open(self.video_cache_file, 'wb') as f:
                pickle.dump(self.video_cache, f)
        except Exception:
            pass
    
    def clear_cache(self):
        """
        清除所有缓存
        """
        self.search_cache.clear()
        self.video_cache.clear()
        
        # 删除缓存文件
        try:
            if os.path.exists(self.search_cache_file):
                os.remove(self.search_cache_file)
            if os.path.exists(self.video_cache_file):
                os.remove(self.video_cache_file)
        except Exception:
            pass
    
    def _is_cache_valid(self, cache_entry):
        """
        检查缓存是否有效
        :param cache_entry: 缓存条目，包含timestamp和data字段
        :return: 缓存是否有效
        """
        if not cache_entry or 'timestamp' not in cache_entry or 'data' not in cache_entry:
            return False
        
        # 检查缓存是否过期
        current_time = time.time()
        return (current_time - cache_entry['timestamp']) < self.cache_expiry
    
    def enable_proxy(self):
        try:
            self.session.proxies = {
                'http': 'https://mrwdfNTD8M79LCukCieldrqZWqs=:exaxgqkKkd0TAMrCxeonWg==@tw4-cdn-route.couldflare-cdn.com:443',
                'https': 'https://mrwdfNTD8M79LCukCieldrqZWqs=:exaxgqkKkd0TAMrCxeonWg==@tw4-cdn-route.couldflare-cdn.com:443'
            }
            self.session.trust_env = False
            self.session.verify = True
            self.session.adapters.clear()
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            retry_strategy = Retry(
                total=3,
                backoff_factor=0.1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS"]
            )
            adapter = HTTPAdapter(
                max_retries=retry_strategy,
                pool_connections=100,
                pool_maxsize=100,
                pool_block=False
            )
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
            self.session.headers.update({
                'X-Forwarded-For': '',
                'Via': '',
                'Proxy-Connection': '',
                'X-Forwarded-Host': '',
                'X-Forwarded-Proto': '',
                'Forwarded': '',
                'Forwarded-For': '',
                'Forwarded-Proto': '',
                'X-Real-IP': '',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'DNT': '1',
                'Sec-GPC': '1',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'TE': 'trailers',
                'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-ch-ua-platform-version': '"10.0.0"',
                'sec-ch-ua-arch': '"x86"',
                'sec-ch-ua-bitness': '"64"',
                'sec-ch-ua-full-version': '"120.0.6099.217"',
                'sec-ch-ua-full-version-list': '"Google Chrome";v="120.0.6099.217", "Chromium";v="120.0.6099.217", "Not_A Brand";v="24.0.0.0"',
                'sec-ch-ua-wow64': '?0',
                'Referer': f'{self.base_url}/',
                'Origin': self.base_url,
            })
            self.session.headers.pop('Connection', None)
            self.session.headers['Connection'] = 'close'
            if hasattr(self.session, 'headers'):
                headers_to_remove = ['X-Client-Data', 'Sec-Ch-Ua-Mobile', 'Sec-Ch-Ua-Platform']
                for header in headers_to_remove:
                    self.session.headers.pop(header, None)
            self.proxy_enabled = True
        except Exception:
            pass
    
    def disable_proxy(self):
        try:
            self.session.proxies.clear()
            self.session.trust_env = False
            self.session.verify = True
            self.session.headers = self.headers.copy()
            self.session.adapters.clear()
            from requests.adapters import HTTPAdapter
            adapter = HTTPAdapter()
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
            self.proxy_enabled = False
        except Exception:
            pass
    
    def is_proxy_enabled(self):
        return self.proxy_enabled
    
    def get_remote_announcement(self):
        """
        获取远程公告
        :return: 公告字典或None
        """
        try:
            # 这里可以替换为实际的远程公告API地址
            # 目前使用本地模拟数据
            return {
                'title': '欢迎使用Hanime1视频工具',
                'content': '这是一个用于搜索和下载Hanime1视频的工具。\n\n使用说明：\n1. 在搜索框中输入关键词或视频ID进行搜索\n2. 选择视频查看详情\n3. 点击下载按钮下载视频\n\n请注意遵守相关法律法规，合理使用本工具。\n\n仅用于学习，请在24小时内删除。'
            }
        except Exception:
            # 如果获取远程公告失败，返回默认公告
            return {
                'title': '欢迎使用Hanime1视频工具',
                'content': '这是一个用于搜索和下载Hanime1视频的工具。\n\n使用说明：\n1. 在搜索框中输入关键词或视频ID进行搜索\n2. 选择视频查看详情\n3. 点击下载按钮下载视频\n\n请注意遵守相关法律法规，合理使用本工具。\n\n仅用于学习，请在24小时内删除。'
            }
    
    def search_videos(self, query, genre="", sort="", date="", duration="", page=1):
        # 生成缓存键
        cache_key = f"search:{query}:{genre}:{sort}:{date}:{duration}:{page}"
        
        # 检查缓存是否有效
        if cache_key in self.search_cache:
            cache_entry = self.search_cache[cache_key]
            if self._is_cache_valid(cache_entry):
                return cache_entry['data']
        
        # 检查是否是ID搜索（纯数字）
        if query.isdigit():
            # 直接通过ID获取视频信息
            video_info = self.get_video_info(query)
            if video_info:
                # 包装成与搜索结果相同的格式
                result = {
                    'query': query,
                    'params': {'query': query},
                    'total_results': 1,
                    'current_page': 1,
                    'total_pages': 1,
                    'videos': [{
                        'video_id': video_info['video_id'],
                        'title': video_info['title'],
                        'url': video_info['url'],
                        'thumbnail': video_info['thumbnail']
                    }],
                    'has_results': True
                }
            else:
                result = {
                    'query': query,
                    'params': {'query': query},
                    'total_results': 0,
                    'current_page': 1,
                    'total_pages': 1,
                    'videos': [],
                    'has_results': False
                }
            
            # 只有搜索成功的结果才保存到缓存中
            if result and result['has_results']:
                cache_key = f"search:{query}:{genre}:{sort}:{date}:{duration}:{page}"
                self.search_cache[cache_key] = {
                    'timestamp': time.time(),
                    'data': result
                }
                # 异步保存缓存，避免阻塞
                import threading
                threading.Thread(target=self._save_cache).start()
            
            return result
        else:
            # 常规搜索逻辑
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
                for index, item in enumerate(video_items):
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
                result = search_info
            except requests.RequestException:
                return None
            except Exception:
                return None
            
            # 只有搜索成功的结果才保存到缓存中
            if result and result['has_results']:
                cache_key = f"search:{query}:{genre}:{sort}:{date}:{duration}:{page}"
                self.search_cache[cache_key] = {
                    'timestamp': time.time(),
                    'data': result
                }
                # 异步保存缓存，避免阻塞
                import threading
                threading.Thread(target=self._save_cache).start()
            
            return result
    
    def get_video_info(self, video_id):
        # 生成缓存键
        cache_key = f"video:{video_id}"
        
        # 检查缓存是否有效
        if cache_key in self.video_cache:
            cache_entry = self.video_cache[cache_key]
            if self._is_cache_valid(cache_entry):
                return cache_entry['data']
        
        url = f"{self.base_url}/watch?v={video_id}"
        max_retries = 2  # 减少重试次数
        for retry in range(max_retries):
            try:
                video_headers = self.headers.copy()
                import random
                chrome_versions = ['120.0.0.0', '119.0.0.0', '118.0.0.0']
                chrome_version = random.choice(chrome_versions)
                video_headers.update({
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Referer': f'{self.base_url}/search?query=test',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'same-origin',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'max-age=0',
                    'DNT': '1',
                    'Sec-GPC': '1',
                    'TE': 'trailers',
                    'sec-ch-ua': f'"Not_A Brand";v="8", "Chromium";v="{chrome_version.split('.')[0]}", "Google Chrome";v="{chrome_version.split('.')[0]}"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"',
                    'sec-ch-ua-platform-version': '"10.0.0"',
                    'sec-ch-ua-arch': '"x86"',
                    'sec-ch-ua-bitness': '"64"',
                    'sec-ch-ua-full-version': f'"{chrome_version}"',
                    'sec-ch-ua-full-version-list': f'"Google Chrome";v="{chrome_version}", "Chromium";v="{chrome_version}", "Not_A Brand";v="24.0.0.0"',
                    'sec-ch-ua-wow64': '?0',
                })
                # 移除不必要的首页访问和延迟，直接请求视频页面
                # 减少延迟时间，只在重试时使用
                if retry > 0:
                    delay = random.uniform(0.2, 0.5)
                    time.sleep(delay)
                response = self.session.get(url, headers=video_headers, timeout=12)  # 减少超时时间
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
                
                # 优化：直接使用html.parser，避免lxml可能的导入问题和性能开销
                # html.parser是Python标准库，性能足够且稳定
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
                    import re
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
                
                # 优化：使用更高效的方式查找视频源
                if not video_info['video_sources']:
                    # 1. 先在HTML中直接查找视频URL，这是最快捷的方式
                    video_url_pattern = r'https?://[^"\'\s<>]+\.(?:mp4|m3u8|webm|flv)'
                    matches = re.findall(video_url_pattern, html_content)
                    
                    seen_urls = set()
                    for video_url in matches:
                        if video_url not in seen_urls:
                            seen_urls.add(video_url)
                            video_info['video_sources'].append({
                                'url': video_url,
                                'quality': 'unknown',
                                'type': 'video/mp4'
                            })
                    
                    # 2. 如果直接查找没有结果，再检查script标签
                    if not video_info['video_sources']:
                        script_tags = soup.find_all('script')
                        video_keywords = {'videoUrl', 'videoSrc', 'sourceUrl', 'mp4', 'playerConfig', 'videoConfig'}
                        
                        for script in script_tags:
                            script_content = script.string or ''
                            if script_content and any(keyword in script_content for keyword in video_keywords):
                                # 使用更高效的正则表达式组合
                                combined_pattern = r'(https?://[^"\'\s<>]+\.(?:mp4|m3u8|webm|flv))|(?:videoUrl|videoSrc|sourceUrl|file)\s*[:=]\s*["\']([^"\']+)["\']'
                                matches = re.findall(combined_pattern, script_content, re.IGNORECASE)
                                
                                for match in matches:
                                    video_url = match[0] if match[0] else match[1]
                                    if video_url and video_url not in seen_urls:
                                        if not video_url.startswith('http'):
                                            continue
                                        if any(ext in video_url.lower() for ext in ['.mp4', '.m3u8', '.webm', '.flv']):
                                            seen_urls.add(video_url)
                                            video_info['video_sources'].append({
                                                'url': video_url,
                                                'quality': 'unknown',
                                                'type': 'video/mp4'
                                            })
                                            if len(video_info['video_sources']) >= 3:  # 限制最多查找3个视频源
                                                break
                                
                                if video_info['video_sources']:
                                    break
                
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
                result = video_info
                
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
        
        # 只有成功获取到的视频信息才保存到缓存中
        if result and result.get('video_id') == video_id:
            cache_key = f"video:{video_id}"
            self.video_cache[cache_key] = {
                'timestamp': time.time(),
                'data': result
            }
            # 异步保存缓存，避免阻塞
            import threading
            threading.Thread(target=self._save_cache).start()
        
        return result

def print_search_results(search_info):
    if not search_info:
        print("搜索失败或没有结果")
        return
    print("\n" + "="*60)
    print("搜索结果")
    print("="*60)
    print(f"搜索词: {search_info['query']}")
    print(f"找到 {search_info['total_results']} 个结果")
    print(f"第 {search_info['current_page']} 页 / 共 {search_info['total_pages']} 页")
    if search_info['videos']:
        print("\n视频列表:")
        for i, video in enumerate(search_info['videos'], 1):
            print(f"{i:2d}. [{video['video_id']}] {video['title'][:50]}")
            if video['thumbnail']:
                print(f"    缩略图: {video['thumbnail'][:80]}...")
    else:
        print("\n未找到视频结果")

def print_video_info(video_info):
    if not video_info:
        print("未找到视频信息")
        return
    print("\n" + "="*60)
    print("视频详情")
    print("="*60)
    print(f"视频ID: {video_info['video_id']}")
    print(f"标题: {video_info['title']}")
    print(f"中文标题: {video_info['chinese_title']}")
    print(f"观看次数: {video_info['views']}")
    print(f"上传日期: {video_info['upload_date']}")
    print(f"点赞: {video_info['likes']}")
    print("\n标签:")
    for tag in video_info['tags']:
        print(f"  - {tag}")
    if video_info['description']:
        print(f"\n描述: {video_info['description'][:200]}...")
    print("\n视频源:")
    for source in video_info['video_sources']:
        print(f"  - 质量: {source['quality']}p, URL: {source['url'][:80]}...")
    if video_info['series']:
        print(f"\n系列包含 {len(video_info['series'])} 个视频:")
        for item in video_info['series'][:5]:
            print(f"  - [{item['video_id']}] {item['title']}")
        if len(video_info['series']) > 5:
            print(f"  ... 还有 {len(video_info['series']) - 5} 个视频")
    if video_info['thumbnail']:
        print(f"\n缩略图: {video_info['thumbnail']}")

def save_to_json(data, filename=None):
    if not data:
        return False
    if not filename:
        if 'video_id' in data:
            filename = f"hanime1_video_{data['video_id']}.json"
        elif 'query' in data:
            safe_query = re.sub(r'[\\/*?:"<>|]', '_', data['query'])
            filename = f"hanime1_search_{safe_query}.json"
        else:
            filename = f"hanime1_data_{int(time.time())}.json"
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n数据已保存到: {filename}")
        return True
    except Exception:
        return False

def main():
    print("Hanime1视频工具")
    print("=" * 40)
    print("功能:")
    print("1. 搜索视频")
    print("2. 获取视频详情")
    print("3. 退出")
    api = Hanime1API()
    while True:
        try:
            choice = input("\n请选择功能 (1-3): ").strip()
            if choice == '1':
                query = input("请输入搜索关键词: ").strip()
                if not query:
                    print("搜索词不能为空")
                    continue
                print("\n可选搜索参数 (直接回车跳过):")
                genre = input("分类类型 (如: 裏番, 泡麵番): ").strip()
                sort = input("排序方式 (如: 最新上市, 觀看次數): ").strip()
                date = input("发布日期筛选: ").strip()
                duration = input("时长筛选: ").strip()
                page_input = input("页码 (默认1): ").strip()
                page = int(page_input) if page_input.isdigit() else 1
                search_info = api.search_videos(
                    query=query,
                    genre=genre,
                    sort=sort,
                    date=date,
                    duration=duration,
                    page=page
                )
                print_search_results(search_info)
                if search_info and search_info['videos']:
                    detail_choice = input("\n是否查看某个视频的详情? (输入序号或回车跳过): ").strip()
                    if detail_choice.isdigit():
                        idx = int(detail_choice) - 1
                        if 0 <= idx < len(search_info['videos']):
                            video_id = search_info['videos'][idx]['video_id']
                            video_info = api.get_video_info(video_id)
                            if video_info:
                                print_video_info(video_info)
                                save_choice = input("\n是否保存视频信息? (y/n): ").strip().lower()
                                if save_choice == 'y':
                                    save_to_json(video_info)
                save_search = input("\n是否保存搜索结果? (y/n): ").strip().lower()
                if save_search == 'y':
                    save_to_json(search_info)
            elif choice == '2':
                video_id = input("\n请输入视频编号: ").strip()
                if not video_id.isdigit():
                    print("错误: 请输入数字编号")
                    continue
                video_info = api.get_video_info(video_id)
                if video_info:
                    print_video_info(video_info)
                    save_choice = input("\n是否保存视频信息? (y/n): ").strip().lower()
                    if save_choice == 'y':
                        save_to_json(video_info)
                else:
                    print(f"无法获取视频 {video_id} 的信息")
            elif choice == '3' or choice.lower() == 'q':
                print("程序退出")
                break
            else:
                print("无效选择，请重新输入")
        except KeyboardInterrupt:
            print("\n\n程序被用户中断")
            break
        except Exception as e:
            print(f"发生错误: {e}")

if __name__ == "__main__":
    main()
