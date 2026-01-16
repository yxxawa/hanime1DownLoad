
import requests
from bs4 import BeautifulSoup
import re
import time
import json
import os
from urllib.parse import urljoin


class Hanime1API:
    # 编译常用的正则表达式，避免在循环中重复编译
    REGEX_VIDEO_ID = re.compile(r'v=(\d+)')
    REGEX_PAGE_NUM = re.compile(r'page=(\d+)')
    REGEX_NEXT_PAGE = re.compile(r'下一頁|下一页|Next|next|>|»', re.IGNORECASE)
    REGEX_VIEW_COUNT = re.compile(r'(觀看次數|观看次数)：([\d.]+)萬次')
    REGEX_DATE = re.compile(r'(\d{4}-\d{2}-\d{2})')
    REGEX_LIKE = re.compile(r'(\d+)%\s*\((\d+)\)')
    REGEX_VIDEO_SOURCE = re.compile(r"const source = '(.*?)'")
    REGEX_TITLE_CLEAN = re.compile(r'\s*[-–]\s*(H動漫|Hanime1|裏番|線上看|me)[:_\s]*.*$', re.IGNORECASE)
    REGEX_TITLE_CLASS = re.compile(r'.*title.*|.*name.*')
    
    def __init__(self):
        self.base_url = "https://hanime1.me"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session = requests.Session()
        
        # 优化session配置，减少连接建立时间
        self.session.headers.update(self.headers)
        self.session.trust_env = True  # 允许使用系统环境配置，包括DNS解析
        self.session.verify = True
        
        # 启用连接池
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,  # 连接池中的最大连接数
            pool_maxsize=10,      # 每个主机的最大连接数
            pool_block=False       # 当连接池耗尽时不阻塞，而是创建新连接
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # 启用HTTP/2支持（如果服务器支持）
        try:
            from urllib3.contrib import pyopenssl
            from urllib3.contrib import _securetransport
            from urllib3.util import ssl_ as ssl_utils
            self.session.headers.update({'Connection': 'Upgrade, HTTP2-Settings'})
        except ImportError:
            pass
        
        # 优化超时设置
        self.session.timeout = (5, 15)  # 连接超时5秒，读取超时15秒
        
        # 加载保存的session
        self.load_session()
    
    def save_session(self):
        """
        保存session信息到settings.json文件
        """
        try:
            # 读取现有的settings
            settings = {}
            if os.path.exists('settings.json'):
                with open('settings.json', 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            
            # 更新session信息
            settings['session'] = {
                'cookies': self.session.cookies.get_dict(),
                'headers': dict(self.session.headers),
                'timestamp': time.time()
            }
            
            # 保存到settings.json
            with open('settings.json', 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            print("Session保存成功到settings.json")
        except Exception as e:
            print(f"Session保存失败: {e}")
    
    def load_session(self):
        """
        从settings.json加载session信息
        """
        try:
            if os.path.exists('settings.json'):
                with open('settings.json', 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
            session_data = settings.get('session', {})
            # 恢复cookies
            for name, value in session_data.get('cookies', {}).items():
                # 为cf_clearance cookie设置正确的domain
                if name == 'cf_clearance':
                    self.session.cookies.set(name, value, domain='.hanime1.me', path='/')
                else:
                    self.session.cookies.set(name, value)
            
            print("Session加载成功")
        except Exception as e:
            print(f"Session加载失败: {e}")
    

    

    
    def search_videos(self, query, page=1):
        """
        搜索视频，使用Han1meViewer-main的代码逻辑
        
        参数:
            query: 搜索关键词
            page: 页码
        """
        # 检查是否是ID搜索
        if query.isdigit():
            video_info = self.get_video_info(query)
            if video_info:
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
            
            return result
        else:
            # 构建搜索参数
            params = {
                'query': query,
                'page': page
            }
            
            try:
                url = f"{self.base_url}/search"
                response = self.session.get(url, params=params, timeout=10)
                
                if response.status_code != 200:
                    return None
            
                html_content = response.text
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # 模仿Han1meViewer-main的搜索结果解析，适配新的页面结构
                videos = []
                video_dict = {}
                
                # 优先查找content-padding-new容器
                video_containers = soup.select('div.content-padding-new div.video-item-container, div.row div.video-item-container')
                
                for container in video_containers:
                    # 查找horizontal-card
                    card = container.find('div', class_='horizontal-card')
                    if not card:
                        continue
                    
                    a_tag = card.find('a')
                    if not a_tag:
                        continue
                    
                    video_link = a_tag['href']
                    if not video_link:
                        continue
                    
                    # 提取视频ID
                    video_id_match = self.REGEX_VIDEO_ID.search(video_link)
                    if not video_id_match:
                        continue
                    video_id = video_id_match.group(1)
                    
                    # 只处理未见过的视频ID
                    if video_id in video_dict:
                        continue
                    
                    # 提取标题 - 查找title类
                    title_element = card.find('div', class_='title')
                    if not title_element:
                        continue
                    title = title_element.text.strip()
                    
                    # 提取封面URL - 查找img标签
                    img = card.find('img')
                    if not img or not img.get('src'):
                        continue
                    cover_url = img['src']
                    
                    # 只保留每个视频ID的一个版本
                    video_dict[video_id] = {
                        'video_id': video_id,
                        'title': title,
                        'url': f"{self.base_url}/watch?v={video_id}",
                        'thumbnail': cover_url
                    }
                
                # 将去重后的视频添加到结果列表
                videos = list(video_dict.values())
                
                # 解析总页数 - 简化逻辑，减少DOM查询
                total_pages = 1
                
                # 1. 查找带有pagination类的ul元素（优先级最高）
                pagination = soup.find('ul', class_='pagination')
                if pagination:
                    # 从分页ul中提取页码
                    page_items = pagination.find_all('li', class_='page-item')
                    page_numbers = []
                    
                    for item in page_items:
                        link = item.find('a', class_='page-link')
                        if not link:
                            continue
                        
                        text = link.get_text().strip()
                        href = link.get('href', '')
                        
                        # 从文本中提取页码
                        if text.isdigit() and len(text) <= 3:
                            page_numbers.append(int(text))
                        
                        # 从href中提取页码
                        page_match = self.REGEX_PAGE_NUM.search(href)
                        if page_match:
                            page_numbers.append(int(page_match.group(1)))
                    
                    if page_numbers:
                        total_pages = max(page_numbers)
                else:
                    # 2. 检查是否有下一页按钮
                    has_next_page = bool(soup.find_all('a', text=self.REGEX_NEXT_PAGE))
                    if has_next_page:
                        total_pages = page + 1
                    
                # 3. 确保总页数至少为1
                total_pages = max(1, total_pages)
                
                result = {
                    'query': query,
                    'params': params,
                    'total_results': len(videos),
                    'current_page': page,
                    'total_pages': total_pages,
                    'videos': videos,
                    'has_results': len(videos) > 0
                }
            
            except Exception as e:
                print(f"搜索错误: {e}")
                return None
            
            return result
    
    def get_video_info(self, video_id):
        """
        获取视频详细信息，使用Han1meViewer-main的代码逻辑
        """
        url = f"{self.base_url}/watch?v={video_id}"
        max_retries = 2
        
        for retry in range(max_retries):
            try:
                response = self.session.get(url, timeout=12)
                
                if response.status_code != 200:
                    return None
                
                html_content = response.text
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
                
                # 解析标题（一次性获取，避免重复查询）
                title_tag = soup.find('title')
                if title_tag:
                    full_title = title_tag.get_text(strip=True)
                    # 移除所有常见的网站后缀
                    cleaned_title = self.REGEX_TITLE_CLEAN.sub('', full_title)
                    video_info['title'] = cleaned_title.strip()
                
                # 解析中文标题
                h3_title = soup.find('h3', {'id': 'shareBtn-title'})
                if h3_title:
                    video_info['chinese_title'] = h3_title.get_text(strip=True)
                
                # 解析观看次数和上传日期
                view_info = soup.find('div', class_='video-description-panel')
                if view_info:
                    panel_text = view_info.get_text(strip=True)
                    view_match = self.REGEX_VIEW_COUNT.search(panel_text)
                    if view_match:
                        video_info['views'] = view_match.group(2) + '萬次'
                    
                    date_match = self.REGEX_DATE.search(panel_text)
                    if date_match:
                        video_info['upload_date'] = date_match.group(1)
                
                # 解析点赞信息
                like_button = soup.find('button', {'id': 'video-like-btn'})
                if like_button:
                    like_text = like_button.get_text(strip=True)
                    match = self.REGEX_LIKE.search(like_text)
                    if match:
                        video_info['likes'] = f"{match.group(1)}% ({match.group(2)}票)"
                
                # 解析视频源（优先从video标签提取）
                video_tag = soup.find('video', {'id': 'player'})
                if video_tag:
                    # 获取封面
                    poster = video_tag.get('poster')
                    if poster:
                        video_info['thumbnail'] = poster
                    
                    # 获取视频源
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
                
                # 如果没有找到视频源，尝试从player-div-wrapper中的JavaScript提取
                if not video_info['video_sources']:
                    player_div_wrapper = soup.find('div', {'id': 'player-div-wrapper'})
                    if player_div_wrapper:
                        scripts = player_div_wrapper.find_all('script')
                        for script in scripts:
                            if script.string:
                                result = self.REGEX_VIDEO_SOURCE.search(script.string)
                                if result:
                                    video_url = result.group(1)
                                    video_info['video_sources'].append({
                                        'url': video_url,
                                        'quality': 'unknown',
                                        'type': 'video/mp4'
                                    })
                                    break  # 找到后立即停止循环
                
                # 解析标签（一次性查询所有标签）
                tags_div = soup.find('div', class_='video-tags-wrapper')
                if tags_div:
                    tag_links = tags_div.find_all('a')
                    tags = []
                    for link in tag_links:
                        tag_text = link.get_text(strip=True)
                        if tag_text and tag_text != '#' and 'http' not in tag_text:
                            tags.append(tag_text)
                    video_info['tags'] = tags  # 一次性赋值，减少属性访问
                
                # 解析描述
                description_div = soup.find('div', class_='video-caption-text')
                if description_div:
                    video_info['description'] = description_div.get_text(strip=True)
                
                # 解析相关视频（优化：先收集所有相关视频，再去重）
                related_videos = soup.find_all('div', class_='related-watch-wrap')
                series = []
                seen_vids = set()
                
                for item in related_videos:
                    link = item.find('a', class_='overlay')
                    if not link or not link.get('href'):
                        continue
                    
                    video_url = link.get('href')
                    match = re.search(r'v=(\d+)', video_url)
                    if not match:
                        continue
                    
                    vid = match.group(1)
                    if vid in seen_vids:
                        continue  # 避免重复处理同一视频
                    seen_vids.add(vid)
                    
                    # 获取标题
                    title_elem = item.find('div', class_=self.REGEX_TITLE_CLASS)
                    title = title_elem.get_text(strip=True) if title_elem else ''
                    if not title:
                        title = item.get('title', '')
                    
                    # 获取缩略图
                    img_tag = item.find('img')
                    thumbnail = img_tag.get('src') if img_tag and img_tag.get('src') else ''
                    
                    # 获取时长
                    duration_div = item.find('div', class_='card-mobile-duration')
                    duration = duration_div.get_text(strip=True) if duration_div else ''
                    
                    series.append({
                        'video_id': vid,
                        'title': title,
                        'chinese_title': title,
                        'url': f"{self.base_url}/watch?v={vid}",
                        'thumbnail': thumbnail,
                        'duration': duration
                    })
                
                video_info['series'] = series  # 一次性赋值，减少属性访问和后续去重
                
                return video_info
            
            except Exception as e:
                if retry < max_retries - 1:
                    time.sleep(1)
                    continue
                return None
