import requests
from bs4 import BeautifulSoup
import re
import json
import time
import os
from urllib.parse import quote, urlencode, urljoin

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
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.session.trust_env = True  # 允许使用系统环境配置，包括DNS解析
        self.session.verify = True
    
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
                
                # 模仿Han1meViewer-main的搜索结果解析
                all_contents_class = soup.find('div', class_='content-padding-new')
                all_simplified_contents_class = soup.find('div', class_='home-rows-videos-wrapper')
                
                videos = []
                if all_contents_class:
                    # 正常搜索结果解析
                    # 使用字典来存储每个视频ID的最佳版本
                    video_dict = {}
                    
                    all_search_divs = all_contents_class.find_all('div', class_='search-doujin-videos')
                    
                    for div in all_search_divs:
                        a_tag = div.find('a')
                        if not a_tag:
                            continue
                        
                        video_link = a_tag['href']
                        if not video_link:
                            continue
                        
                        # 提取视频ID
                        video_id_match = re.search(r'v=(\d+)', video_link)
                        if not video_id_match:
                            continue
                        video_id = video_id_match.group(1)
                        
                        # 查找card-mobile-panel
                        panel = div.find('div', class_=re.compile(r'card-mobile-panel'))
                        if not panel:
                            continue
                        
                        # 提取标题
                        title_elements = panel.select('div[class=card-mobile-title]')
                        if not title_elements:
                            continue
                        title = title_elements[0].text.strip()
                        
                        # 提取封面URL
                        img_elements = panel.select('img')
                        if len(img_elements) < 2:
                            continue
                        cover_url = img_elements[1]['src']
                        if not cover_url:
                            continue
                        
                        # 只保留每个视频ID的一个版本
                        if video_id not in video_dict:
                            video_dict[video_id] = {
                                'video_id': video_id,
                                'title': title,
                                'url': f"{self.base_url}/watch?v={video_id}",
                                'thumbnail': cover_url
                            }
                    
                    # 将去重后的视频添加到结果列表
                    videos = list(video_dict.values())
                elif all_simplified_contents_class:
                    # 简化搜索结果解析
                    video_items = all_simplified_contents_class.children
                    for item in video_items:
                        if item.name != 'a':
                            continue
                        
                        video_link = item['href']
                        video_id = re.search(r'v=(\d+)', video_link).group(1) if video_link else None
                        cover_url = item.select('img')[0]['src'] if item.select('img') else None
                        title = item.select('div[class$=title]')[0].text.strip() if item.select('div[class$=title]') else None
                        
                        if video_id and cover_url and title:
                            videos.append({
                                'video_id': video_id,
                                'title': title,
                                'url': f"{self.base_url}/watch?v={video_id}",
                                'thumbnail': cover_url
                            })
                
                # 解析总页数
                total_pages = 1
                
                # 1. 查找所有包含页码的链接
                all_links = soup.find_all('a', href=True)
                page_numbers = []
                
                for link in all_links:
                    href = link.get('href', '')
                    text = link.get_text().strip()
                    
                    # 从文本中提取页码
                    if text.isdigit() and len(text) <= 3:  # 页码通常是1-3位数字
                        page_numbers.append(int(text))
                    
                    # 从href中提取页码
                    page_match = re.search(r'page=(\d+)', href)
                    if page_match:
                        page_numbers.append(int(page_match.group(1)))
                
                # 2. 查找带有pagination类的ul元素
                pagination = soup.find('ul', class_='pagination')
                if pagination:
                    # 从分页ul中提取页码
                    page_items = pagination.find_all('li', class_='page-item')
                    for item in page_items:
                        link = item.find('a', class_='page-link')
                        if link:
                            text = link.get_text().strip()
                            if text.isdigit() and len(text) <= 3:
                                page_numbers.append(int(text))
                            
                            href = link.get('href', '')
                            page_match = re.search(r'page=(\d+)', href)
                            if page_match:
                                page_numbers.append(int(page_match.group(1)))
                
                # 3. 计算总页数
                if page_numbers:
                    # 去重并获取最大值
                    unique_pages = list(set(page_numbers))
                    total_pages = max(unique_pages)
                else:
                    # 检查是否有下一页按钮
                    next_patterns = [r'下一頁', r'下一页', r'Next', r'next', r'>', r'»']
                    has_next_page = False
                    
                    for pattern in next_patterns:
                        next_buttons = soup.find_all('a', text=re.compile(pattern, re.IGNORECASE))
                        if next_buttons:
                            has_next_page = True
                            break
                    
                    # 如果有下一页按钮，总页数至少是当前页+1
                    if has_next_page:
                        total_pages = page + 1
                    else:
                        # 默认总页数为1
                        total_pages = 1
                
                # 4. 确保总页数至少为1
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
                    if response.status_code == 403:
                        self.session.cookies.clear()
                        time.sleep(1)
                        continue
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
                
                # 解析标题
                title_tag = soup.find('title')
                if title_tag:
                    full_title = title_tag.get_text(strip=True)
                    if ' - Hanime1' in full_title:
                        video_info['title'] = full_title.split(' - Hanime1')[0].strip()
                    elif ' - H動漫' in full_title:
                        video_info['title'] = full_title.split(' - H動漫')[0].strip()
                    else:
                        video_info['title'] = full_title
                
                # 解析中文标题
                h3_title = soup.find('h3', {'id': 'shareBtn-title'})
                if h3_title:
                    video_info['chinese_title'] = h3_title.get_text(strip=True)
                
                # 解析观看次数和上传日期
                view_info = soup.find('div', class_='video-description-panel')
                if view_info:
                    panel_text = view_info.get_text(strip=True)
                    view_match = re.search(r'(觀看次數|观看次数)：([\d.]+)萬次', panel_text)
                    if view_match:
                        video_info['views'] = view_match.group(2) + '萬次'
                    
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', panel_text)
                    if date_match:
                        video_info['upload_date'] = date_match.group(1)
                
                # 解析点赞信息
                like_button = soup.find('button', {'id': 'video-like-btn'})
                if like_button:
                    like_text = like_button.get_text(strip=True)
                    match = re.search(r'(\d+)%\s*\((\d+)\)', like_text)
                    if match:
                        video_info['likes'] = f"{match.group(1)}% ({match.group(2)}票)"
                
                # 解析视频源
                # 1. 从video标签提取
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
                
                # 2. 从player-div-wrapper中的JavaScript提取
                if not video_info['video_sources']:
                    player_div_wrapper = soup.find('div', {'id': 'player-div-wrapper'})
                    if player_div_wrapper:
                        scripts = player_div_wrapper.find_all('script')
                        video_source_regex = re.compile(r"const source = '(.*?)'")
                        for script in scripts:
                            data = script.string
                            if data:
                                result = video_source_regex.search(data)
                                if result:
                                    video_url = result.group(1)
                                    video_info['video_sources'].append({
                                        'url': video_url,
                                        'quality': 'unknown',
                                        'type': 'video/mp4'
                                    })
                                    break
                
                # 解析标签
                tags_div = soup.find('div', class_='video-tags-wrapper')
                if tags_div:
                    tag_links = tags_div.find_all('a')
                    for link in tag_links:
                        tag_text = link.get_text(strip=True)
                        if tag_text and tag_text != '#' and 'http' not in tag_text:
                            video_info['tags'].append(tag_text)
                
                # 解析描述
                description_div = soup.find('div', class_='video-caption-text')
                if description_div:
                    video_info['description'] = description_div.get_text(strip=True)
                
                # 解析相关视频
                related_videos = soup.find_all('div', class_='related-watch-wrap')
                for item in related_videos:
                    link = item.find('a', class_='overlay')
                    if link and link.get('href'):
                        video_url = link.get('href')
                        match = re.search(r'v=(\d+)', video_url)
                        if match:
                            vid = match.group(1)
                            title = item.get('title', '')
                            
                            # 尝试获取中文标题
                            title_elem = item.find('div', class_=re.compile(r'.*title.*|.*name.*'))
                            if title_elem:
                                title_text = title_elem.get_text(strip=True)
                                if title_text:
                                    title = title_text
                            
                            # 获取缩略图
                            img_tag = item.find('img')
                            thumbnail = img_tag.get('src') if img_tag and img_tag.get('src') else ''
                            
                            # 获取时长
                            duration_div = item.find('div', class_='card-mobile-duration')
                            duration = duration_div.get_text(strip=True) if duration_div else ''
                            
                            video_info['series'].append({
                                'video_id': vid,
                                'title': title,
                                'chinese_title': title,
                                'url': f"{self.base_url}/watch?v={vid}",
                                'thumbnail': thumbnail,
                                'duration': duration
                            })
                
                # 去重相关视频
                seen = set()
                unique_series = []
                for item in video_info['series']:
                    if item['video_id'] not in seen:
                        seen.add(item['video_id'])
                        unique_series.append(item)
                video_info['series'] = unique_series
                
                return video_info
            
            except Exception as e:
                if retry < max_retries - 1:
                    time.sleep(1)
                    continue
                return None
        
        return None
