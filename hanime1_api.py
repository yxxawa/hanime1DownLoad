import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import quote, urlencode
import time
import logging
import os
import glob

# 初始化时清理旧的HTML响应文件
def cleanup_old_html_files():
    """清理旧的HTML响应文件"""
    # 获取所有搜索和视频响应HTML文件
    search_files = glob.glob('search_response_*.html')
    video_files = glob.glob('video_response_*.html')
    
    # 合并所有要删除的文件
    all_files = search_files + video_files
    
    # 删除文件
    for file in all_files:
        try:
            os.remove(file)
            logging.debug(f"已删除旧的HTML文件: {file}")
        except Exception as e:
            logging.error(f"删除文件 {file} 失败: {e}")

# 执行清理
cleanup_old_html_files()

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='hanime1_api.log',
    filemode='a'  # 追加模式
)

logger = logging.getLogger('Hanime1API')

class Hanime1API:
    def __init__(self):
        self.base_url = "https://hanime1.me"
        # 改进请求头，使用更真实的浏览器指纹
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',  # 不接受brotli压缩
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
            # 添加更真实的浏览器指纹
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-ch-ua-platform-version': '"10.0.0"',
            'sec-ch-ua-arch': '"x86"',
            'sec-ch-ua-bitness': '"64"',
            'sec-ch-ua-full-version': '"120.0.6099.217"',
            'sec-ch-ua-full-version-list': '"Google Chrome";v="120.0.6099.217", "Chromium";v="120.0.6099.217", "Not_A Brand";v="24.0.0.0"',
            'sec-ch-ua-wow64': '?0',
            # 添加更多的浏览器指纹
            'X-Requested-With': 'XMLHttpRequest',
            'X-Real-IP': '127.0.0.1',
            'X-Forwarded-For': '127.0.0.1',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # 配置代理连接选项，增强隐蔽性
        # 1. 禁用代理头，避免暴露代理信息
        self.session.trust_env = False
        
        # 2. 配置SSL验证选项
        self.session.verify = True  # 启用SSL验证
        
        # 3. 添加更多的伪装头，避免被检测为代理
        self.session.headers.update({
            'X-Forwarded-For': '',  # 清除可能的代理转发头
            'Via': '',  # 清除代理路径头
            'Proxy-Connection': '',  # 清除代理连接头
        })
        
        # 代理配置（tw2）- 根据Clash配置修改
        # Clash配置：type: http, tls: true
        # 测试发现：使用https://前缀才能成功连接，因为代理服务器启用了TLS加密
        self.proxy_config = {
            'http': 'https://mrwdfNTD8M79LCukCieldrqZWqs=:exaxgqkKkd0TAMrCxeonWg==@tw4-cdn-route.couldflare-cdn.com:443',
            'https': 'https://mrwdfNTD8M79LCukCieldrqZWqs=:exaxgqkKkd0TAMrCxeonWg==@tw4-cdn-route.couldflare-cdn.com:443'
        }
        
        # 默认关闭代理
        self.proxy_enabled = False
        self.session.proxies = {}
        logger.info("Hanime1API 初始化完成，代理默认关闭")
        
        # 添加更多的反反爬虫措施
        self.session.cookies.set('cf_clearance', '')  # 尝试清除可能的Cloudflare clearance cookie
        logger.info("Hanime1API 初始化完成")
    
    def enable_proxy(self):
        """
        启用代理
        """
        try:
            # 1. 设置代理配置
            self.session.proxies = {
                'http': 'https://mrwdfNTD8M79LCukCieldrqZWqs=:exaxgqkKkd0TAMrCxeonWg==@tw4-cdn-route.couldflare-cdn.com:443',
                'https': 'https://mrwdfNTD8M79LCukCieldrqZWqs=:exaxgqkKkd0TAMrCxeonWg==@tw4-cdn-route.couldflare-cdn.com:443'
            }
            
            # 2. 确保代理连接选项正确配置，增强隐蔽性
            self.session.trust_env = False
            self.session.verify = True
            
            # 3. 添加代理优化配置，避免速度限制
            self.session.adapters.clear()
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry
            
            # 配置重试策略
            retry_strategy = Retry(
                total=3,
                backoff_factor=0.1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS"]
            )
            
            # 配置适配器，增加连接池大小
            adapter = HTTPAdapter(
                max_retries=retry_strategy,
                pool_connections=100,
                pool_maxsize=100,
                pool_block=False
            )
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
            
            # 4. 清除可能暴露代理的头，添加反检测头
            self.session.headers.update({
                # 清除代理相关头
                'X-Forwarded-For': '',
                'Via': '',
                'Proxy-Connection': '',
                'X-Forwarded-Host': '',
                'X-Forwarded-Proto': '',
                'Forwarded': '',
                'Forwarded-For': '',
                'Forwarded-Proto': '',
                'X-Real-IP': '',
                
                # 添加浏览器指纹增强
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
                
                # 添加更真实的浏览器特征
                'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                
                # Chrome 120 特定头
                'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"Windows"',
                'sec-ch-ua-platform-version': '"10.0.0"',
                'sec-ch-ua-arch': '"x86"',
                'sec-ch-ua-bitness': '"64"',
                'sec-ch-ua-full-version': '"120.0.6099.217"',
                'sec-ch-ua-full-version-list': '"Google Chrome";v="120.0.6099.217", "Chromium";v="120.0.6099.217", "Not_A Brand";v="24.0.0.0"',
                'sec-ch-ua-wow64': '?0',
                
                # 增加请求多样性，避免被识别为机器人
                'Referer': f'{self.base_url}/',
                'Origin': self.base_url,
            })
            
            # 5. 添加更多反检测配置
            # 禁用连接池复用，每次请求使用新连接
            self.session.headers.pop('Connection', None)
            self.session.headers['Connection'] = 'close'
            
            # 禁用 SSL 指纹识别
            if hasattr(self.session, 'headers'):
                # 移除可能暴露客户端的头
                headers_to_remove = ['X-Client-Data', 'Sec-Ch-Ua-Mobile', 'Sec-Ch-Ua-Platform']
                for header in headers_to_remove:
                    self.session.headers.pop(header, None)
            
            self.proxy_enabled = True
            logger.info("已启用代理: tw4-cdn-route.couldflare-cdn.com")
        except Exception as e:
            logger.error(f"启用代理时出错: {e}")
    
    def disable_proxy(self):
        """
        禁用代理
        """
        try:
            # 1. 清除代理配置
            self.session.proxies.clear()
            
            # 2. 恢复默认连接选项
            self.session.trust_env = False
            self.session.verify = True
            
            # 3. 恢复原始头配置
            self.session.headers = self.headers.copy()
            
            # 4. 恢复适配器配置
            self.session.adapters.clear()
            from requests.adapters import HTTPAdapter
            adapter = HTTPAdapter()
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
            
            self.proxy_enabled = False
            logger.info("已禁用代理")
        except Exception as e:
            logger.error(f"禁用代理时出错: {e}")
    
    def is_proxy_enabled(self):
        """
        检查代理是否已启用
        
        Returns:
            bool: 代理是否已启用
        """
        return self.proxy_enabled
    
    def search_videos(self, query, genre="", sort="", date="", duration="", page=1):
        """
        搜索视频
        
        Args:
            query (str): 搜索关键词
            genre (str): 分类类型
            sort (str): 排序方式
            date (str): 发布日期筛选
            duration (str): 时长筛选
            page (int): 页码
        
        Returns:
            dict: 搜索结果
        """
        # 构建搜索参数
        params = {
            'query': query,
            'type': '',  # 搜索类型（视频/作者）
            'genre': genre,
            'sort': sort,
            'date': date,
            'duration': duration,
            'page': page if page > 1 else None  # 第一页通常省略page参数
        }
        
        # 移除空值参数
        params = {k: v for k, v in params.items() if v}
        
        try:
            logger.info(f"开始搜索视频，关键词: {query}, 页码: {page}")
            url = f"{self.base_url}/search"
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"搜索请求失败，状态码: {response.status_code}")
                return None
            
            # 检查响应headers
            logger.debug(f"响应Headers: {response.headers}")
            
            # 手动处理响应内容
            html_content = None
            
            # 检查是否使用了brotli压缩
            content_encoding = response.headers.get('Content-Encoding', '').lower()
            logger.debug(f"Content-Encoding: {content_encoding}")
            
            try:
                if 'br' in content_encoding:
                    # 手动解压缩brotli内容，添加更健壮的错误处理
                    try:
                        import brotli
                        html_content = brotli.decompress(response.content).decode('utf-8')
                        logger.debug("使用brotli手动解压缩成功")
                    except Exception as brotli_error:
                        logger.error(f"brotli解码失败: {brotli_error}")
                        # 尝试直接使用requests自动处理，即使headers显示br编码
                        logger.debug("尝试使用requests自动解码brotli响应")
                        response.encoding = 'utf-8'
                        html_content = response.text
                else:
                    # 使用requests自动处理
                    response.encoding = 'utf-8'
                    html_content = response.text
                    logger.debug("使用requests自动解码")
            except Exception as e:
                logger.error(f"解码响应内容时出错: {e}")
                # 即使解码失败，也尝试继续处理，可能部分内容可用
                logger.debug("尝试使用原始响应内容继续处理")
                try:
                    html_content = response.text
                except:
                    logger.error("无法获取任何响应内容")
                    return None
            
            logger.debug("开始解析搜索响应")
            
            # 检查HTML内容是否包含关键字符
            if not html_content or '<html' not in html_content.lower() and '<!doctype' not in html_content.lower():
                logger.error(f"HTML内容可能损坏或未正确解码，长度: {len(html_content) if html_content else 0} 字符")
                if html_content:
                    logger.debug(f"前100个字符: {html_content[:100]}")
                return None
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 提取搜索信息
            search_info = {
                'query': query,
                'params': params,
                'total_results': 0,
                'current_page': page,
                'total_pages': 1,
                'videos': [],
                'has_results': False
            }
            
            # 1. 直接查找所有搜索视频项目，不依赖于特定容器
            # 不再保存HTML响应到文件，避免占用磁盘空间
            
            # 查找所有带有search-doujin-videos类的div元素
            video_items = soup.find_all('div', class_='search-doujin-videos')
            logger.debug(f"找到 {len(video_items)} 个视频项目")
            
            # 搜索HTML中是否包含'search-doujin-videos'字符串
            if 'search-doujin-videos' in response.text:
                logger.debug(f"HTML中包含'search-doujin-videos'字符串，出现次数: {response.text.count('search-doujin-videos')}")
            else:
                logger.debug("HTML中不包含'search-doujin-videos'字符串")
            
            # 添加更多调试日志，保存第一个视频项目的HTML
            if video_items:
                logger.debug(f"第一个视频项目的HTML: {str(video_items[0])[:500]}...")
            
            for index, item in enumerate(video_items):
                logger.debug(f"处理第 {index+1} 个视频项目")
                
                # 从每个视频项目中提取链接
                # 查找带有overlay类的a标签
                video_link = item.find('a', class_='overlay')
                logger.debug(f"找到视频链接: {video_link}，类型: {type(video_link)}")
                
                if video_link and hasattr(video_link, 'attrs') and 'href' in video_link.attrs:
                    logger.debug(f"视频链接href: {video_link['href']}")
                    
                    # 提取视频ID
                    match = re.search(r'v=(\d+)', video_link['href'])
                    logger.debug(f"视频ID匹配结果: {match}")
                    
                    if match:
                        video_id = match.group(1)
                        logger.debug(f"提取到视频ID: {video_id}")
                        
                        # 避免重复添加同一视频
                        if any(v['video_id'] == video_id for v in search_info['videos']):
                            logger.debug(f"视频 {video_id} 已存在，跳过")
                            continue
                        
                        # 提取标题（从div的title属性获取，这是最完整的标题）
                        title = item.get('title', f"视频 {video_id}")
                        logger.debug(f"提取到标题: {title}")
                        
                        # 提取缩略图
                        # 查找所有img标签，获取第一个有src属性的图片作为缩略图
                        img_tags = item.find_all('img')
                        logger.debug(f"找到 {len(img_tags)} 个图片标签")
                        thumbnail = ""
                        for img in img_tags:
                            if img.get('src'):
                                logger.debug(f"图片src: {img.get('src')}")
                                if 'thumbnail' in img.get('src'):
                                    thumbnail = img.get('src')
                                    break
                        # 如果没有找到带thumbnail的图片，使用第一个有src的图片
                        if not thumbnail and img_tags:
                            for img in img_tags:
                                if img.get('src'):
                                    thumbnail = img.get('src')
                                    break
                        logger.debug(f"提取到缩略图: {thumbnail}")
                        
                        # 添加到搜索结果
                        search_info['videos'].append({
                            'video_id': video_id,
                            'title': title,
                            'url': f"{self.base_url}/watch?v={video_id}",
                            'thumbnail': thumbnail
                        })
                        logger.debug(f"已添加视频 {video_id} 到结果列表")
                else:
                    logger.debug(f"未找到有效视频链接")
            
            # 3. 如果上面没找到，尝试通用搜索作为备选方案
            if not search_info['videos']:
                logger.debug("通过search-doujin-videos未找到视频，尝试备选搜索方案")
                # 查找所有可能的视频链接
                all_links = soup.find_all('a', href=re.compile(r'/watch\?v=\d+'))
                logger.debug(f"备选方案找到 {len(all_links)} 个链接")
                for link in all_links:
                    match = re.search(r'v=(\d+)', link['href'])
                    if match:
                        video_id = match.group(1)
                        # 避免重复
                        if not any(v['video_id'] == video_id for v in search_info['videos']):
                            # 尝试获取标题
                            # 查找链接周围的标题元素
                            title_elem = link.find(class_=re.compile(r'.*title.*|.*name.*'))
                            title = title_elem.get_text(strip=True) if title_elem else f"视频 {video_id}"
                            
                            # 尝试获取缩略图
                            img = link.find('img')
                            thumbnail = img.get('src') if img else ''
                            
                            search_info['videos'].append({
                                'video_id': video_id,
                                'title': title,
                                'url': f"{self.base_url}/watch?v={video_id}",
                                'thumbnail': thumbnail
                            })
            
            # 3. 提取分页信息
            pagination = soup.find('div', class_='search-pagination')
            if pagination:
                # 尝试提取页码信息
                page_links = pagination.find_all('a', href=re.compile(r'.*page=\d+.*'))
                if page_links:
                    page_numbers = []
                    for link in page_links:
                        text = link.get_text(strip=True)
                        if text.isdigit():
                            page_numbers.append(int(text))
                    
                    if page_numbers:
                        search_info['total_pages'] = max(page_numbers)
            
            # 4. 检查是否有"跳转到页面"表单
            skip_form = soup.find('form', {'id': 'skip-page-form'})
            if skip_form:
                # 提取总页数
                total_div = skip_form.find('div', string=re.compile(r'/\s*\d+'))
                if total_div:
                    match = re.search(r'/(d+)', total_div.get_text())
                    if match:
                        search_info['total_pages'] = int(match.group(1))
            
            search_info['total_results'] = len(search_info['videos'])
            search_info['has_results'] = len(search_info['videos']) > 0
            
            logger.info(f"搜索完成，找到 {search_info['total_results']} 个结果，共 {search_info['total_pages']} 页")
            return search_info
            
        except requests.RequestException as e:
            logger.error(f"搜索请求错误: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"搜索解析错误: {e}", exc_info=True)
            return None
    
    def get_video_info(self, video_id):
        """
        获取视频详细信息
        
        Args:
            video_id (str): 视频编号
        
        Returns:
            dict: 视频信息
        """
        url = f"{self.base_url}/watch?v={video_id}"
        
        # 重试机制，最多重试3次
        max_retries = 3
        for retry in range(max_retries):
            try:
                logger.info(f"开始获取视频 {video_id} 的信息 (重试 {retry+1}/{max_retries})")
                logger.debug(f"视频详情请求URL: {url}")
                
                # 为视频页面请求添加更完整的请求头，模仿真实浏览器
                video_headers = self.headers.copy()
                # 每次请求时随机化一些请求头，增加真实性
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
                    # 添加更真实的浏览器指纹
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
                
                # 先发送一个简单的请求获取Cookie，然后再请求视频详情
                logger.debug("先获取主页Cookie")
                home_response = self.session.get(self.base_url, headers=video_headers, timeout=10)
                logger.debug(f"主页响应状态码: {home_response.status_code}")
                
                # 添加随机延迟，避免请求过快
                delay = random.uniform(0.5, 1.5)
                logger.debug(f"添加延迟 {delay:.2f}秒")
                time.sleep(delay)
                
                # 现在请求视频详情
                logger.debug("请求视频详情页面")
                response = self.session.get(url, headers=video_headers, timeout=15)
                logger.debug(f"视频详情响应状态码: {response.status_code}")
                logger.debug(f"视频详情响应Headers: {response.headers}")
                
                if response.status_code != 200:
                    logger.error(f"获取视频 {video_id} 信息失败，状态码: {response.status_code}")
                    logger.debug(f"响应内容: {response.text[:500]}...")
                    # 不再保存错误响应到文件，避免占用磁盘空间
                    
                    # 如果是403错误，尝试清除Cookie并重新设置
                    if response.status_code == 403:
                        logger.debug("403错误，尝试清除Cookie并重新设置")
                        self.session.cookies.clear()
                        # 添加随机延迟后重试
                        time.sleep(random.uniform(1, 2))
                        continue
                    
                    return None
                
                # 改进响应处理，确保正确解码
                html_content = None
                content_encoding = response.headers.get('Content-Encoding', '').lower()
                logger.debug(f"视频详情响应Content-Encoding: {content_encoding}")
                
                try:
                    if 'br' in content_encoding:
                        # 手动解压缩brotli内容
                        import brotli
                        html_content = brotli.decompress(response.content).decode('utf-8')
                        logger.debug("使用brotli手动解压缩成功")
                    elif 'gzip' in content_encoding:
                        # 使用gzip解压缩
                        import gzip
                        try:
                            # 检查内容是否真的是gzip格式（以0x1f 0x8b开头）
                            if response.content.startswith(b'\x1f\x8b'):
                                html_content = gzip.decompress(response.content).decode('utf-8')
                                logger.debug("使用gzip手动解压缩成功")
                            else:
                                # 不是有效的gzip格式，直接使用text
                                logger.warning("响应头显示gzip编码，但内容不是有效的gzip格式，尝试直接解码")
                                response.encoding = 'utf-8'
                                html_content = response.text
                                logger.debug("使用requests自动解码")
                        except (gzip.BadGzipFile, OSError, EOFError) as e:
                            logger.error(f"gzip解压失败: {e}")
                            # 解压失败，尝试直接使用text
                            response.encoding = 'utf-8'
                            html_content = response.text
                            logger.debug("gzip解压失败，使用requests自动解码")
                    elif 'deflate' in content_encoding:
                        # 使用deflate解压缩
                        import zlib
                        try:
                            html_content = zlib.decompress(response.content).decode('utf-8')
                            logger.debug("使用deflate手动解压缩成功")
                        except Exception as e:
                            logger.error(f"deflate解压失败: {e}")
                            # 解压失败，尝试直接使用text
                            response.encoding = 'utf-8'
                            html_content = response.text
                            logger.debug("deflate解压失败，使用requests自动解码")
                    else:
                        # 使用requests自动处理
                        response.encoding = 'utf-8'
                        html_content = response.text
                        logger.debug("使用requests自动解码")
                except Exception as e:
                    logger.error(f"解码视频详情响应时出错: {e}")
                    # 如果解码失败，尝试使用原始内容
                    html_content = response.text
                    logger.debug("使用原始内容继续处理")
                
                # 检查HTML内容是否有效
                if not html_content or '<html' not in html_content.lower():
                    logger.error(f"视频详情HTML内容无效，长度: {len(html_content) if html_content else 0}")
                    continue
                
                # 使用更可靠的解析器，如果可用的话
                logger.debug("开始解析视频详情响应")
                try:
                    soup = BeautifulSoup(html_content, 'lxml')
                    logger.debug("使用lxml解析器")
                except:
                    soup = BeautifulSoup(html_content, 'html.parser')
                    logger.debug("使用html.parser解析器")
                
                # 提取视频信息
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
                
                # 1. 提取标题
                title_tag = soup.find('title')
                if title_tag:
                    full_title = title_tag.get_text(strip=True)
                    if ' - Hanime1' in full_title:
                        video_info['title'] = full_title.split(' - Hanime1')[0].strip()
                    elif ' - H動漫' in full_title:
                        video_info['title'] = full_title.split(' - H動漫')[0].strip()
                    else:
                        video_info['title'] = full_title
                
                # 2. 提取中文标题（从h3标签）
                h3_title = soup.find('h3', {'id': 'shareBtn-title'})
                if h3_title:
                    video_info['chinese_title'] = h3_title.get_text(strip=True)
                
                # 3. 提取观看次数和上传日期
                view_info = soup.find('div', class_='video-description-panel')
                if view_info:
                    # 直接从整个面板文本中提取信息，不依赖特定的子元素
                    panel_text = view_info.get_text(strip=True)
                    logger.debug(f"视频描述面板文本: {panel_text}")
                    
                    # 提取观看次数
                    import re
                    view_match = re.search(r'观看次数：([\d.]+万次)', panel_text)
                    if view_match:
                        video_info['views'] = view_match.group(1)
                        logger.debug(f"提取到观看次数: {video_info['views']}")
                    
                    # 提取上传日期
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', panel_text)
                    if date_match:
                        video_info['upload_date'] = date_match.group(1)
                        logger.debug(f"提取到上传日期: {video_info['upload_date']}")
                
                # 4. 提取点赞信息
                like_button = soup.find('button', {'id': 'video-like-btn'})
                if like_button:
                    like_text = like_button.get_text(strip=True)
                    logger.debug(f"点赞按钮文本: {like_text}")
                    # 使用空格而不是&nbsp;
                    match = re.search(r'(\d+%)\s*\((\d+)\)', like_text)
                    if match:
                        video_info['likes'] = f"{match.group(1)} ({match.group(2)}票)"
                        logger.debug(f"提取到点赞信息: {video_info['likes']}")
                
                # 5. 提取视频源 - 改进版本
                # 首先尝试直接查找video标签
                video_tag = soup.find('video', {'id': 'player'})
                if video_tag:
                    # 获取封面图
                    poster = video_tag.get('poster')
                    if poster:
                        video_info['thumbnail'] = poster
                        logger.debug(f"提取到缩略图: {video_info['thumbnail']}")
                    
                    # 获取视频源
                    sources = video_tag.find_all('source')
                    logger.debug(f"找到 {len(sources)} 个视频源")
                    for source in sources:
                        src = source.get('src')
                        if src:
                            # 确保是完整的URL
                            if not src.startswith('http'):
                                # 如果是相对URL，转换为绝对URL
                                from urllib.parse import urljoin
                                src = urljoin(self.base_url, src)
                            video_info['video_sources'].append({
                                'url': src,
                                'quality': source.get('size', 'unknown'),
                                'type': source.get('type', 'video/mp4')
                            })
                
                # 改进：如果直接查找video标签没有找到视频源，尝试从JavaScript代码中提取
                if not video_info['video_sources']:
                    logger.debug("从HTML中直接查找video标签失败，尝试从JavaScript代码中提取视频源")
                    
                    # 查找包含视频源信息的script标签
                    script_tags = soup.find_all('script')
                    for script in script_tags:
                        script_content = script.string or ''
                        if script_content:
                            # 查找可能包含视频URL的关键词
                            if any(keyword in script_content for keyword in ['videoUrl', 'videoSrc', 'sourceUrl', 'mp4', 'playerConfig', 'videoConfig']):
                                logger.debug(f"找到可能包含视频源的script标签，长度: {len(script_content)}")
                                
                                # 尝试多种正则表达式提取视频URL
                                # 匹配各种格式的视频URL
                                video_url_patterns = [
                                    # 直接匹配URL
                                    r'https?://[^"\'\s<>]+\.(?:mp4|m3u8|webm|flv)',
                                    # 匹配JavaScript变量赋值
                                    r'(?:videoUrl|videoSrc|sourceUrl|file)\s*[:=]\s*["\']([^"\']+)["\']',
                                    # 匹配JSON格式中的URL
                                    r'["\'](https?://[^"\']+\.(?:mp4|m3u8|webm))["\']',
                                    # 匹配HTML source标签格式
                                    r'<source[^>]+src=["\']([^"\']+)["\']'
                                ]
                                
                                for pattern in video_url_patterns:
                                    matches = re.findall(pattern, script_content, re.IGNORECASE)
                                    if matches:
                                        logger.debug(f"使用模式 {pattern} 找到 {len(matches)} 个匹配")
                                        for match in matches:
                                            # 如果匹配是元组，取第一个元素
                                            video_url = match[0] if isinstance(match, tuple) else match
                                            # 确保是完整的URL
                                            if not video_url.startswith('http'):
                                                continue
                                            # 确保是视频URL（过滤掉其他类型的URL）
                                            if not any(ext in video_url.lower() for ext in ['.mp4', '.m3u8', '.webm', '.flv']):
                                                continue
                                            # 避免重复添加
                                            if not any(source['url'] == video_url for source in video_info['video_sources']):
                                                video_info['video_sources'].append({
                                                    'url': video_url,
                                                    'quality': 'unknown',
                                                    'type': 'video/mp4'  # 默认类型
                                                })
                                                logger.debug(f"从JavaScript中提取到视频源: {video_url}")
                                
                                # 如果已经找到视频源，提前退出循环
                                if video_info['video_sources']:
                                    break
                
                # 6. 如果还是没有找到视频源，尝试从整个HTML中搜索
                if not video_info['video_sources']:
                    logger.debug("从script标签中提取视频源失败，尝试从整个HTML中搜索")
                    # 从整个HTML中搜索视频URL
                    video_url_pattern = r'(https?://[^"\'\s<>]+\.(?:mp4|m3u8|webm|flv))'
                    matches = re.findall(video_url_pattern, html_content)
                    if matches:
                        logger.debug(f"从整个HTML中找到 {len(matches)} 个视频URL匹配")
                        for video_url in matches:
                            if not any(source['url'] == video_url for source in video_info['video_sources']):
                                video_info['video_sources'].append({
                                    'url': video_url,
                                    'quality': 'unknown',
                                    'type': 'video/mp4'
                                })
                                logger.debug(f"从整个HTML中提取到视频源: {video_url}")
                
                # 7. 提取标签
                tags_div = soup.find('div', class_='video-tags-wrapper')
                if tags_div:
                    # 查找所有a标签，它们直接包含标签文本
                    tag_links = tags_div.find_all('a')
                    logger.debug(f"找到 {len(tag_links)} 个标签链接")
                    for link in tag_links:
                        tag_text = link.get_text(strip=True)
                        if tag_text and tag_text != '#' and 'http' not in tag_text:
                            video_info['tags'].append(tag_text)
                    logger.debug(f"提取到标签: {video_info['tags']}")
                
                # 8. 提取描述
                description_div = soup.find('div', class_='video-caption-text')
                if description_div:
                    video_info['description'] = description_div.get_text(strip=True)
                    logger.debug(f"提取到描述: {video_info['description'][:100]}...")
                
                # 9. 提取系列信息（播放列表）
                playlist_items = soup.find_all('div', class_='related-watch-wrap')
                logger.debug(f"找到 {len(playlist_items)} 个相关视频")
                series_info = []
                
                for item in playlist_items:
                    link = item.find('a', class_='overlay')
                    if link and link.get('href'):
                        video_url = link.get('href')
                        match = re.search(r'v=(\d+)', video_url)
                        if match:
                            vid = match.group(1)
                            
                            # 从item的title属性获取标题
                            title = item.get('title', '')
                            
                            # 提取中文标题 - 相关视频的中文标题通常直接在title属性中
                            # 或者可能需要从其他元素获取
                            chinese_title = title  # 先假设title包含中文标题
                            
                            # 尝试从其他位置获取更准确的中文标题
                            # 查找可能包含中文标题的元素
                            title_elem = item.find('div', class_=re.compile(r'.*title.*|.*name.*'))
                            if title_elem:
                                title_text = title_elem.get_text(strip=True)
                                if title_text:
                                    chinese_title = title_text
                            
                            # 获取缩略图
                            img_tag = item.find('img')
                            thumbnail = img_tag.get('src') if img_tag and img_tag.get('src') else ''
                            
                            # 获取时长
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
                
                # 去重
                seen = set()
                unique_series = []
                for item in series_info:
                    if item['video_id'] not in seen:
                        seen.add(item['video_id'])
                        unique_series.append(item)
                
                video_info['series'] = unique_series
                logger.debug(f"提取到 {len(unique_series)} 个相关视频")
                logger.info(f"成功获取视频 {video_id} 的信息")
                return video_info
                
            except requests.RequestException as e:
                logger.error(f"获取视频 {video_id} 信息时网络请求错误: {e}", exc_info=True)
                # 如果不是最后一次重试，继续重试
                if retry < max_retries - 1:
                    logger.info(f"网络请求错误，{max_retries - retry - 1} 次重试机会，等待后重试")
                    time.sleep(random.uniform(1, 2))
                    continue
                return None
            except Exception as e:
                logger.error(f"获取视频 {video_id} 信息时解析错误: {e}", exc_info=True)
                # 如果不是最后一次重试，继续重试
                if retry < max_retries - 1:
                    logger.info(f"解析错误，{max_retries - retry - 1} 次重试机会，等待后重试")
                    time.sleep(random.uniform(1, 2))
                    continue
                return None

def print_search_results(search_info):
    """打印搜索结果"""
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
        print("提示: 搜索结果可能通过JavaScript动态加载，程序可能无法直接获取")

def print_video_info(video_info):
    """打印视频信息"""
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
    """保存数据为JSON文件"""
    if not data:
        return False
    
    if not filename:
        if 'video_id' in data:
            filename = f"hanime1_video_{data['video_id']}.json"
        elif 'query' in data:
            # 清理文件名中的非法字符
            safe_query = re.sub(r'[\\/*?:"<>|]', '_', data['query'])
            filename = f"hanime1_search_{safe_query}.json"
        else:
            filename = f"hanime1_data_{int(time.time())}.json"
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\n数据已保存到: {filename}")
        return True
    except Exception as e:
        print(f"保存文件时出错: {e}")
        return False

def main():
    """主函数"""
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
                # 搜索功能
                query = input("请输入搜索关键词: ").strip()
                if not query:
                    print("搜索词不能为空")
                    continue
                
                # 可选搜索参数
                print("\n可选搜索参数 (直接回车跳过):")
                genre = input("分类类型 (如: 裏番, 泡麵番): ").strip()
                sort = input("排序方式 (如: 最新上市, 觀看次數): ").strip()
                date = input("发布日期筛选: ").strip()
                duration = input("时长筛选: ").strip()
                page_input = input("页码 (默认1): ").strip()
                page = int(page_input) if page_input.isdigit() else 1
                
                # 执行搜索
                search_info = api.search_videos(
                    query=query,
                    genre=genre,
                    sort=sort,
                    date=date,
                    duration=duration,
                    page=page
                )
                
                # 显示结果
                print_search_results(search_info)
                
                if search_info and search_info['videos']:
                    # 询问是否查看详情
                    detail_choice = input("\n是否查看某个视频的详情? (输入序号或回车跳过): ").strip()
                    if detail_choice.isdigit():
                        idx = int(detail_choice) - 1
                        if 0 <= idx < len(search_info['videos']):
                            video_id = search_info['videos'][idx]['video_id']
                            video_info = api.get_video_info(video_id)
                            if video_info:
                                print_video_info(video_info)
                                
                                # 询问是否保存
                                save_choice = input("\n是否保存视频信息? (y/n): ").strip().lower()
                                if save_choice == 'y':
                                    save_to_json(video_info)
                
                # 询问是否保存搜索结果
                save_search = input("\n是否保存搜索结果? (y/n): ").strip().lower()
                if save_search == 'y':
                    save_to_json(search_info)
            
            elif choice == '2':
                # 获取视频详情
                video_id = input("\n请输入视频编号: ").strip()
                
                if not video_id.isdigit():
                    print("错误: 请输入数字编号")
                    continue
                
                video_info = api.get_video_info(video_id)
                
                if video_info:
                    print_video_info(video_info)
                    
                    # 询问是否保存
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
    # 安装所需库的命令:
    # pip install requests beautifulsoup4
    
    main()