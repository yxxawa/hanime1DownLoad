"""
Hanime1API 模块

与Hanime1网站交互的API客户端，提供视频搜索、获取视频信息、管理会话和Cookie等功能。
"""

import json
import logging
import os
import re
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from zhconv import convert


# 处理 PyInstaller 打包后的环境路径问题
def _setup_cert_path():
    """设置 SSL 证书路径"""
    try:
        import certifi
        cert_path = certifi.where()
        if cert_path and os.path.exists(cert_path):
            os.environ["REQUESTS_CA_BUNDLE"] = cert_path
            os.environ["SSL_CERT_FILE"] = cert_path
            logging.info(f"使用 certifi 证书: {cert_path}")
            return
    except ImportError:
        pass

    if hasattr(sys, "_MEIPASS"):
        cert_path = os.path.join(sys._MEIPASS, "certifi", "cacert.pem")
        if os.path.exists(cert_path):
            os.environ["REQUESTS_CA_BUNDLE"] = cert_path
            os.environ["SSL_CERT_FILE"] = cert_path
            logging.info(f"使用打包内证书: {cert_path}")
            return

    logging.warning("未找到 SSL 证书，使用系统默认证书")

_setup_cert_path()


class Hanime1API:
    """
    与Hanime1网站交互的API客户端类

    功能：
    - 视频搜索
    - 获取视频详细信息
    - 会话管理
    - Cookie管理
    """

    # 编译常用的正则表达式，避免在循环中重复编译
    REGEX_VIDEO_ID = re.compile(r"v=(\d+)")
    REGEX_PAGE_NUM = re.compile(r"page=(\d+)")
    REGEX_NEXT_PAGE = re.compile(r"下一頁|下一页|>|»")
    REGEX_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
    REGEX_LIKE = re.compile(r"(\d+)%\s*\((\d+)\)")
    REGEX_VIDEO_SOURCE = re.compile(r"const source = '(.*?)'")
    REGEX_TITLE_CLEAN = re.compile(r"\s*[-–]\s*(H動漫|裏番|線上看)[:_\s]*.*$")
    REGEX_TITLE_CLASS = re.compile(r".*title.*|.*name.*")

    def __init__(self):
        self.base_url = "https://hanime1.me"
        # 内置默认请求头
        self.default_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
                "image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        # 初始化session
        self.session = requests.Session()

        # 启用连接池
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,  # 连接池中的最大连接数
            pool_maxsize=10,  # 每个主机的最大连接数
            pool_block=False,  # 当连接池耗尽时不阻塞，而是创建新连接
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # 设置超时
        self.session.timeout = (5, 15)  # 连接超时5秒，读取超时15秒

        # 加载保存的session和请求头
        self.load_session()

        # 如果settings中没有请求头，使用默认请求头
        if not hasattr(self, "headers") or not self.headers:
            self.headers = self.default_headers.copy()

        # 更新session的headers
        self.session.headers.update(self.headers)

        # 搜索缓存：{(query, page, json_filter_params): (timestamp, result)}
        self.search_cache = {}
        self.cache_ttl = 300  # 缓存有效期 5 分钟

    def _convert_to_simplified(self, text):
        """将繁体中文转换为简体中文"""
        try:
            return convert(text, "zh-cn")
        except Exception as e:
            logging.warning(f"繁简转换失败: {e}")
            return text

    def _get_cache_key(self, query, page, filter_params):
        """生成缓存键"""
        # 将筛选参数转换为可哈希的字符串
        filter_str = json.dumps(filter_params, sort_keys=True) if filter_params else ""
        return (query, page, filter_str)

    def save_session(self):
        """保存session信息和请求头到config/settings.json文件"""
        try:
            # 确保config目录存在
            config_dir = os.path.join(os.getcwd(), "config")
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
            
            # 使用config目录中的settings.json文件
            settings_file = os.path.join(config_dir, "settings.json")
            settings = {}
            if os.path.exists(settings_file):
                with open(settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)

            cookie_dict = {}
            for cookie in self.session.cookies:
                cookie_dict[cookie.name] = {
                    "value": cookie.value,
                    "domain": cookie.domain,
                    "path": cookie.path,
                    "expires": cookie.expires,
                    "secure": cookie.secure,
                    "httponly": getattr(cookie, "httponly", False),
                }

            settings["headers"] = self.headers
            settings["session"] = {"cookies": cookie_dict, "timestamp": time.time()}

            with open(settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.warning(f"Failed to save session: {e}")

    def load_session(self):
        """从config/settings.json加载session信息和请求头"""
        try:
            # 确保config目录存在
            config_dir = os.path.join(os.getcwd(), "config")
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
            
            # 使用config目录中的settings.json文件
            settings_file = os.path.join(config_dir, "settings.json")
            if not os.path.exists(settings_file):
                return

            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)

            # 加载请求头
            self.headers = settings.get("headers", {})

            session_data = settings.get("session", {})
            cookie_dict = session_data.get("cookies", {})

            if cookie_dict:
                # 处理两种cookie格式：旧格式（直接是name:value字典）和新格式（包含完整属性）
                for name, cookie_info in cookie_dict.items():
                    try:
                        if isinstance(cookie_info, dict):
                            # 新格式：包含完整属性
                            self.session.cookies.set(
                                name,
                                cookie_info["value"],
                                domain=cookie_info.get("domain", ".hanime1.me"),
                                path=cookie_info.get("path", "/"),
                                expires=cookie_info.get("expires"),
                                secure=cookie_info.get("secure", True)
                            )
                        else:
                            # 旧格式：直接是值
                            self.session.cookies.set(
                                name, cookie_info, domain=".hanime1.me", path="/"
                            )
                    except Exception as e:
                        logging.warning(f"Failed to load cookie {name}: {e}")
                        continue
        except Exception as e:
            logging.warning(f"Failed to load session: {e}")
            # 如果加载失败，尝试清理旧的settings.json文件
            try:
                config_dir = os.path.join(os.getcwd(), "config")
                settings_file = os.path.join(config_dir, "settings.json")
                os.rename(settings_file, os.path.join(config_dir, "settings.json.backup"))
            except Exception as e:
                logging.warning(f"Failed to backup settings.json: {e}")

    def set_cf_clearance(self, cf_clearance_value):
        """手动设置cf_clearance cookie，这是Cloudflare反爬虫保护的关键

        参数:
            cf_clearance_value: cf_clearance cookie的值
        """
        if cf_clearance_value:
            self.session.cookies.set(
                "cf_clearance",
                cf_clearance_value,
                domain=".hanime1.me",
                path="/",
                secure=True
            )
            # 保存session，以便下次使用
            self.save_session()
        else:
            # 如果值为空，移除cf_clearance cookie
            self.session.cookies.clear()
            # 保存session，以便下次使用
            self.save_session()

    def search_videos(self, query, page=1, filter_params=None):
        """搜索视频

        参数:
            query: 搜索关键词
            page: 页码
            filter_params: 筛选参数
        """
        # 检查缓存
        cache_key = self._get_cache_key(query, page, filter_params)
        if cache_key in self.search_cache:
            timestamp, cached_result = self.search_cache[cache_key]
            if time.time() - timestamp < self.cache_ttl:
                return cached_result
            else:
                del self.search_cache[cache_key]

        # 检查是否是 ID 搜索
        if query.isdigit():
            video_info = self.get_video_info(query)
            if video_info:
                result = {
                    "query": query,
                    "params": {"query": query},
                    "total_results": 1,
                    "current_page": 1,
                    "total_pages": 1,
                    "videos": [
                        {
                            "video_id": video_info["video_id"],
                            "title": video_info["title"],
                            "url": video_info["url"],
                            "thumbnail": video_info["thumbnail"],
                        }
                    ],
                    "has_results": True,
                }
            else:
                result = {
                    "query": query,
                    "params": {"query": query},
                    "total_results": 0,
                    "current_page": 1,
                    "total_pages": 1,
                    "videos": [],
                    "has_results": False,
                }

            return result

        # 构建搜索参数
        params = {"query": query, "page": page}

        # 添加筛选参数
        if filter_params:
            if filter_params.get("genre"):
                params["genre"] = filter_params["genre"]
            if filter_params.get("sort"):
                params["sort"] = filter_params["sort"]
            if filter_params.get("date"):
                params["date"] = filter_params["date"]
            if filter_params.get("duration"):
                params["duration"] = filter_params["duration"]
            # 处理广泛配对参数
            if "broad" in filter_params:
                if filter_params["broad"]:
                    params["broad"] = "on"
                else:
                    # 关的时候值是空，从params中移除broad参数
                    if "broad" in params:
                        del params["broad"]
            # 添加标签参数
            tags = filter_params.get("tags", [])
            if tags:
                params["tags[]"] = tags

        try:
            url = f"{self.base_url}/search"
            response = self.session.get(url, params=params, timeout=10)

            if response.status_code != 200:
                return None

            html_content = response.text

            # 检测Cloudflare验证页面
            cloudflare_patterns = ["正在验证您是否是真人", "hanime1.me正在验证", "请稍候…"]
            if any(pattern in html_content for pattern in cloudflare_patterns):
                raise Exception("Cloudflare 验证拦截")

            soup = BeautifulSoup(html_content, "html.parser")

            # 搜索结果解析
            videos = []
            video_dict = {}

            # 检查当前的影片类型
            current_genre = filter_params.get("genre", "") if filter_params else ""

            # 根据类型使用不同的容器选择器
            if current_genre in ["裏番", "泡麵番"]:
                # 裏番和泡麵番使用特殊的容器结构，需要从#home-rows-wrapper中查找
                video_links = soup.select('#home-rows-wrapper a[href*="/watch?v="]')

                for a_tag in video_links:
                    # 提取视频链接
                    video_link = a_tag["href"]
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

                    # 提取标题
                    card = a_tag.find("div", class_="home-rows-videos-div search-videos")
                    if not card:
                        continue

                    title_element = card.find("div", class_="home-rows-videos-title")
                    if not title_element:
                        continue
                    title = self._convert_to_simplified(title_element.text.strip())

                    # 提取封面URL
                    img = card.find("img")
                    if not img or not img.get("src"):
                        continue
                    cover_url = img["src"]

                    # 添加到结果中
                    video_dict[video_id] = {
                        "video_id": video_id,
                        "title": title,
                        "url": f"{self.base_url}/watch?v={video_id}",
                        "thumbnail": cover_url,
                    }
            else:
                # 其他类型使用常规的容器结构
                video_containers = soup.select(
                    "div.content-padding-new div.video-item-container, "
                    "div.row div.video-item-container"
                )

                for container in video_containers:
                    # 查找horizontal-card
                    card = container.find("div", class_="horizontal-card")
                    if not card:
                        # 尝试查找其他可能的卡片类名
                        card = container.find("div", class_=re.compile(r"card|video-item"))
                    if not card:
                        continue

                    a_tag = card.find("a")
                    if not a_tag:
                        continue

                    video_link = a_tag["href"]
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

                    # 提取标题
                    title_element = card.find("div", class_="title")
                    if not title_element:
                        # 尝试查找其他可能的标题元素
                        title_element = (
                            card.find("h3")
                            or card.find("h4")
                            or card.find("div", class_=re.compile(r"title|name"))
                        )
                    if not title_element:
                        continue
                    title = self._convert_to_simplified(title_element.text.strip())

                    # 提取封面URL
                    img = card.find("img")
                    if not img or not img.get("src"):
                        continue
                    cover_url = img["src"]

                    # 添加到结果中
                    video_dict[video_id] = {
                        "video_id": video_id,
                        "title": title,
                        "url": f"{self.base_url}/watch?v={video_id}",
                        "thumbnail": cover_url,
                    }

            # 将去重后的视频添加到结果列表
            videos = list(video_dict.values())

            # 解析总页数
            def extract_page_numbers():
                """提取页面中的所有页码信息"""
                page_numbers = []

                # 1. 优先查找带有pagination类的分页组件
                pagination = soup.find("ul", class_="pagination")
                if pagination:
                    for item in pagination.find_all("li", class_="page-item"):
                        link = item.find("a", class_="page-link")
                        if not link:
                            continue

                        text = link.get_text().strip()
                        href = link.get("href", "")

                        # 从文本和链接中提取页码
                        if text.isdigit() and len(text) <= 3:
                            page_numbers.append(int(text))

                        page_match = self.REGEX_PAGE_NUM.search(href)
                        if page_match:
                            page_numbers.append(int(page_match.group(1)))

                # 2. 查找所有链接，提取更多页码信息（作为备选方案）
                for link in soup.find_all("a", href=True):
                    href = link.get("href")
                    text = link.get_text().strip()

                    page_match = self.REGEX_PAGE_NUM.search(href)
                    if page_match:
                        page_numbers.append(int(page_match.group(1)))
                    elif text.isdigit() and len(text) <= 3:
                        page_numbers.append(int(text))

                return list(set(page_numbers))  # 去重

            def has_next_page_button():
                """检查是否存在下一页按钮"""
                # 方式1：使用正则表达式匹配"下一頁"、"下一页"等文本
                next_links = soup.find_all("a", text=self.REGEX_NEXT_PAGE)
                for link in next_links:
                    href = link.get("href", "")
                    text = link.get_text().strip()
                    if "上一页" not in text and ("page" in href or any(keyword in text for keyword in ["下一", ">"])):
                        return True
                
                # 方式2：查找包含>、»等箭头符号的链接
                arrow_links = soup.find_all("a", text=re.compile(r"[>»]"))
                for link in arrow_links:
                    href = link.get("href", "")
                    text = link.get_text().strip()
                    if "<" not in text and "‹" not in text and ("page" in href or len(text.strip()) <= 2):
                        return True
                
                # 方式3：查找带有next、paging、pagination等class的按钮
                next_buttons = soup.find_all("a", {"class": re.compile(r"next|paging|pagination")})
                for button in next_buttons:
                    href = button.get("href", "")
                    text = button.get_text().strip()
                    if "上一页" not in text and "<" not in text and ("page" in href or any(keyword in text for keyword in ["下一", ">"])):
                        return True
                
                return False

            # 提取页码并计算总页数
            unique_page_numbers = extract_page_numbers()
            has_next = has_next_page_button()

            # 计算总页数
            if unique_page_numbers:
                # 如果有页码列表，总页数为最大页码
                calculated_total_pages = max(unique_page_numbers)
                # 检查当前页是否可能是最后一页（避免页码显示不完整的情况）
                if has_next and page >= calculated_total_pages:
                    calculated_total_pages = page
            elif has_next:
                # 如果有下一页按钮但没有页码列表，总页数为当前页+1
                calculated_total_pages = page + 1
            else:
                # 如果没有下一页按钮，当前页就是最后一页
                calculated_total_pages = page

            # 确保总页数至少为1
            total_pages = max(1, calculated_total_pages)

            result = {
                "query": query,
                "params": params,
                "total_results": len(videos),
                "current_page": page,
                "total_pages": total_pages,
                "videos": videos,
                "has_results": len(videos) > 0,
            }

            # 存入缓存
            self.search_cache[cache_key] = (time.time(), result)

        except Exception as e:
            print(f"搜索出错: {str(e)}")
            return None

        return result

    def get_video_info(self, video_id, visibility_settings=None):
        """获取视频详细信息

        参数:
            video_id: 视频ID
            visibility_settings: 字段解析控制设置，为None时解析所有字段
        """
        url = f"{self.base_url}/watch?v={video_id}"
        max_retries = 2

        # 默认全部解析
        if visibility_settings is None:
            visibility_settings = {
                "title": True,
                "upload_date": True,
                "likes": True,
                "duration": True,
                "views": True,
                "tags": True,
                "cover": True,
                "description": True,
                "related_videos": True,
            }

        for retry in range(max_retries):
            try:
                response = self.session.get(url, timeout=12)
                if response.status_code != 200:
                    return None

                html_content = response.text
                soup = BeautifulSoup(html_content, "html.parser")

                video_info = {
                    "video_id": video_id,
                    "url": url,
                    "title": "",
                    "description": "",
                    "upload_date": "",
                    "likes": "",
                    "duration": "",
                    "views": "",
                    "video_sources": [],
                    "tags": [],
                    "series": [],
                    "thumbnail": "",
                }

                # 解析标题
                if visibility_settings.get("title", True):
                    title_tag = soup.find("title")
                    if title_tag:
                        full_title = title_tag.get_text(strip=True)
                        cleaned_title = self.REGEX_TITLE_CLEAN.sub("", full_title)
                        video_info["title"] = self._convert_to_simplified(cleaned_title.strip())

                # 解析上传日期
                if visibility_settings.get("upload_date", True):
                    view_info = soup.find("div", class_="video-description-panel")
                    if view_info:
                        panel_text = view_info.get_text(strip=True)
                        date_match = self.REGEX_DATE.search(panel_text)
                        if date_match:
                            video_info["upload_date"] = date_match.group(1)

                # 解析点赞信息
                if visibility_settings.get("likes", True):
                    like_button = soup.find("button", {"id": "video-like-btn"})
                    if like_button:
                        like_text = like_button.get_text(strip=True)
                        match = self.REGEX_LIKE.search(like_text)
                        if match:
                            video_info["likes"] = f"{match.group(1)}% ({match.group(2)}票)"

                # 解析视频时长
                if visibility_settings.get("duration", True):
                    duration_div = soup.find("div", class_="card-mobile-duration")
                    if duration_div:
                        video_info["duration"] = duration_div.get_text(strip=True)

                # 解析观看次数
                if visibility_settings.get("views", True):
                    panel = soup.find("div", class_="video-description-panel")
                    if panel:
                        panel_text = panel.get_text()
                        panel_text = self._convert_to_simplified(panel_text)
                        view_match = re.search(r'观看次数[：:]\s*([\d.]+[万]?[次]?)', panel_text)
                        if view_match:
                            video_info["views"] = view_match.group(1)
                        else:
                            video_info["views"] = "-"

                # 解析视频源（即使不显示也要解析，因为下载需要）
                video_tag = soup.find("video", {"id": "player"})
                if video_tag:
                    # 获取封面 (仅在需要时解析)
                    if visibility_settings.get("cover", True):
                        poster = video_tag.get("poster")
                        if poster:
                            video_info["thumbnail"] = poster

                    # 获取视频源
                    sources = video_tag.find_all("source")
                    for source in sources:
                        src = source.get("src")
                        if src:
                            if not src.startswith("http"):
                                src = urljoin(self.base_url, src)

                            # 解析质量值
                            quality = source.get("size", "unknown")
                            quality_num = 0
                            if isinstance(quality, str):
                                quality_str = quality.lower().replace("p", "")
                                try:
                                    quality_num = int(quality_str)
                                except ValueError:
                                    quality_num = 0
                            elif isinstance(quality, int):
                                quality_num = quality

                            video_info["video_sources"].append(
                                {
                                    "url": src,
                                    "quality": quality,
                                    "quality_num": quality_num,
                                    "type": source.get("type", "video/mp4"),
                                }
                            )

                # 如果没有找到视频源，尝试从player-div-wrapper中的JavaScript提取
                if not video_info["video_sources"]:
                    player_div_wrapper = soup.find("div", {"id": "player-div-wrapper"})
                    if player_div_wrapper:
                        scripts = player_div_wrapper.find_all("script")
                        for script in scripts:
                            if script.string:
                                # 使用正则表达式从JavaScript代码中提取视频源URL
                                result = self.REGEX_VIDEO_SOURCE.search(script.string)
                                if result:
                                    video_url = result.group(1)
                                    video_info["video_sources"].append(
                                        {
                                            "url": video_url,
                                            "quality": "unknown",
                                            "quality_num": 0,
                                            "type": "video/mp4",
                                        }
                                    )
                                    break

                # 对视频源按照质量从高到低排序
                video_info["video_sources"].sort(key=lambda x: x["quality_num"], reverse=True)

                # 解析标签
                if visibility_settings.get("tags", True):
                    tags_div = soup.find("div", class_="video-tags-wrapper")
                    if tags_div:
                        tag_links = tags_div.find_all("a")
                        tags = []
                        for link in tag_links:
                            tag_text = link.get_text(strip=True)
                            if tag_text and tag_text != "#" and "http" not in tag_text:
                                tags.append(self._convert_to_simplified(tag_text))
                        video_info["tags"] = tags

                # 解析描述
                if visibility_settings.get("description", True):
                    description_div = soup.find("div", class_="video-caption-text")
                    if description_div:
                        description_text = description_div.get_text(strip=True)
                        video_info["description"] = self._convert_to_simplified(description_text)

                # 解析相关视频
                if visibility_settings.get("related_videos", True):
                    related_videos = soup.find_all("div", class_="related-watch-wrap")
                    series = []
                    seen_vids = set()

                    for item in related_videos:
                        link = item.find("a", class_="overlay")
                        if not link or not link.get("href"):
                            continue

                        video_url = link.get("href")
                        match = re.search(r"v=(\d+)", video_url)
                        if not match:
                            continue

                        vid = match.group(1)
                        if vid in seen_vids:
                            continue
                        seen_vids.add(vid)

                        # 获取标题
                        title_elem = item.find("div", class_=self.REGEX_TITLE_CLASS)
                        title = (
                            title_elem.get_text(strip=True) if title_elem else item.get("title", "")
                        )
                        title = self._convert_to_simplified(title)

                        # 获取缩略图
                        img_tag = item.find("img")
                        thumbnail = img_tag.get("src") if img_tag and img_tag.get("src") else ""

                        # 获取时长
                        duration_div = item.find("div", class_="card-mobile-duration")
                        duration = duration_div.get_text(strip=True) if duration_div else ""

                        series.append(
                            {
                                "video_id": vid,
                                "title": title,
                                "url": f"{self.base_url}/watch?v={vid}",
                                "thumbnail": thumbnail,
                                "duration": duration,
                            }
                        )
                    video_info["series"] = series

                return video_info

            except Exception as e:
                print(f"获取视频详情出错 (ID: {video_id}): {str(e)}")
                if retry < max_retries - 1:
                    time.sleep(1)
                    continue
                return None
