import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QPushButton, QLineEdit, QListWidget, QLabel, QSplitter, 
    QGroupBox, QFormLayout, QTextEdit, QComboBox, QSpinBox, QRadioButton,
    QProgressBar, QMenu, QAction, QScrollArea, QCheckBox
)
from PyQt5.QtCore import Qt, QThread, QRunnable, QThreadPool, pyqtSignal, pyqtSlot, QObject
from PyQt5.QtGui import QPixmap, QImage
from hanime1_api import Hanime1API

class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)
    progress = pyqtSignal(dict)

class SearchWorker(QRunnable):
    def __init__(self, api, query, genre="", sort="", date="", duration="", page=1):
        super().__init__()
        self.api = api
        self.query = query
        self.genre = genre
        self.sort = sort
        self.date = date
        self.duration = duration
        self.page = page
        self.signals = WorkerSignals()
    
    @pyqtSlot()
    def run(self):
        try:
            result = self.api.search_videos(
                query=self.query,
                genre=self.genre,
                sort=self.sort,
                date=self.date,
                duration=self.duration,
                page=self.page
            )
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()

class GetVideoInfoWorker(QRunnable):
    def __init__(self, api, video_id):
        super().__init__()
        self.api = api
        self.video_id = video_id
        self.signals = WorkerSignals()
    
    @pyqtSlot()
    def run(self):
        try:
            result = self.api.get_video_info(self.video_id)
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()

class DownloadWorker(QRunnable):
    def __init__(self, url, filename, save_path=".", num_threads=4, proxy_config=None):
        super().__init__()
        self.url = url
        self.filename = filename
        self.save_path = save_path
        self.num_threads = num_threads
        self.proxy_config = proxy_config
        self.signals = WorkerSignals()
        self.is_cancelled = False
        self.total_size = 0
        self.downloaded_size = 0
        self.chunk_size = 0
        self.can_use_range = True
        import threading
        self.threading = threading
    
    @pyqtSlot()
    def run(self):
        try:
            import os
            import requests
            
            os.makedirs(self.save_path, exist_ok=True)
            self.full_path = os.path.join(self.save_path, self.filename)
            
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            proxies = self.proxy_config if self.proxy_config else None
            
            response = requests.head(self.url, headers=headers, proxies=proxies, timeout=10)
            response.raise_for_status()
            
            content_length = response.headers.get('content-length')
            self.total_size = int(content_length) if content_length else 0
            
            accept_ranges = response.headers.get('accept-ranges', 'none')
            self.can_use_range = accept_ranges.lower() == 'bytes' and self.total_size > 0
            
            if self.can_use_range:
                self.chunk_size = self.total_size // self.num_threads
                if self.chunk_size < 1024 * 1024:
                    self.num_threads = 1
                    self.chunk_size = self.total_size
                
                self.temp_files = []
                for i in range(self.num_threads):
                    self.temp_files.append(f"{self.full_path}.part{i}")
                
                ranges = []
                for i in range(self.num_threads):
                    start = i * self.chunk_size
                    end = start + self.chunk_size - 1 if i < self.num_threads - 1 else self.total_size - 1
                    ranges.append((start, end))
                
                threads = []
                for i in range(self.num_threads):
                    t = self.threading.Thread(target=self.download_chunk, args=(i, ranges[i]))
                    threads.append(t)
                
                for t in threads:
                    t.start()
                
                for t in threads:
                    t.join()
                
                if self.is_cancelled:
                    self.cleanup_temp_files()
                    self.signals.error.emit("下载已取消")
                    return
                
                self.merge_chunks()
                self.cleanup_temp_files()
            else:
                self.download_single_thread()
                if self.is_cancelled:
                    if os.path.exists(self.full_path):
                        os.remove(self.full_path)
                    self.signals.error.emit("下载已取消")
                    return
            
            self.signals.finished.emit()
            
        except Exception as e:
            self.is_cancelled = True
            self.cleanup_temp_files()
            self.signals.error.emit(str(e))
    
    def download_chunk(self, index, range_tuple):
        import requests
        import os
        
        start, end = range_tuple
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Range': f'bytes={start}-{end}'
        }
        
        try:
            proxies = self.proxy_config if self.proxy_config else None
            response = requests.get(self.url, headers=headers, proxies=proxies, stream=True, timeout=30)
            response.raise_for_status()
            
            chunk_size = 8192
            chunk_downloaded = 0
            
            with open(self.temp_files[index], 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if self.is_cancelled:
                        return
                    
                    if chunk:
                        f.write(chunk)
                        chunk_downloaded += len(chunk)
                        
                        with self.threading.Lock():
                            self.downloaded_size += len(chunk)
                            progress = (self.downloaded_size / self.total_size) * 100
                            self.signals.progress.emit({"progress": progress, "filename": self.filename, "size": self.downloaded_size, "total_size": self.total_size})
        except Exception as e:
            self.is_cancelled = True
            self.signals.error.emit(str(e))
    
    def download_single_thread(self):
        import requests
        import os
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        
        try:
            proxies = self.proxy_config if self.proxy_config else None
            response = requests.get(self.url, headers=headers, proxies=proxies, stream=True, timeout=30)
            response.raise_for_status()
            
            content_length = response.headers.get('content-length')
            if content_length:
                self.total_size = int(content_length)
            
            chunk_size = 8192
            
            with open(self.full_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if self.is_cancelled:
                        return
                    
                    if chunk:
                        f.write(chunk)
                        self.downloaded_size += len(chunk)
                        
                        if self.total_size > 0:
                            progress = (self.downloaded_size / self.total_size) * 100
                        else:
                            progress = min(99.0, (self.downloaded_size / (1024 * 1024)) % 100)
                        
                        self.signals.progress.emit({"progress": progress, "filename": self.filename, "size": self.downloaded_size, "total_size": self.total_size})
        except Exception as e:
            self.is_cancelled = True
            self.signals.error.emit(str(e))
    
    def merge_chunks(self):
        import os
        
        try:
            with open(self.full_path, 'wb') as f:
                for temp_file in self.temp_files:
                    if os.path.exists(temp_file):
                        with open(temp_file, 'rb') as tf:
                            f.write(tf.read())
        except Exception as e:
            self.is_cancelled = True
            self.signals.error.emit(f"合并文件失败: {str(e)}")
    
    def cleanup_temp_files(self):
        import os
        
        if hasattr(self, 'temp_files'):
            for temp_file in self.temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
    
    def cancel(self):
        self.is_cancelled = True

class FilterDialog(QDialog):
    def __init__(self, parent=None, filters=None):
        super().__init__(parent)
        self.setWindowTitle("搜索筛选")
        self.setGeometry(100, 100, 500, 600)
        self.filters = filters or {
            'keyword': '',
            'genre': '全部',
            'sort': '最新上市',
            'date': '全部',
            'duration': '全部',
            'properties': [],
            'relationship': [],
            'character_setting': [],
            'appearance_body': [],
            'scene_location': [],
            'story_plot': [],
            'sexual_position': []
        }
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(15)
        
        keyword_layout = QHBoxLayout()
        keyword_layout.addWidget(QLabel("关键词:"))
        self.keyword_input = QLineEdit(self.filters.get('keyword', ''))
        self.keyword_input.setPlaceholderText("请输入搜索关键词...")
        keyword_layout.addWidget(self.keyword_input)
        scroll_layout.addLayout(keyword_layout)
        
        genre_group = QGroupBox("影片类型")
        genre_layout = QGridLayout(genre_group)
        genre_options = ["全部", "里番", "泡面番", "Motion Anime", "3DCG", "2.5D", "2D动画", "AI生成", "MMD", "Cosplay"]
        self.genre_buttons = []
        for i, genre in enumerate(genre_options):
            radio_button = QRadioButton(genre)
            if genre == self.filters.get('genre', '全部'):
                radio_button.setChecked(True)
            self.genre_buttons.append((genre, radio_button))
            genre_layout.addWidget(radio_button, i // 2, i % 2)
        scroll_layout.addWidget(genre_group)
        
        properties_group = QGroupBox("影片属性")
        properties_layout = QGridLayout(properties_group)
        properties_options = ["无码", "AI解码", "中文字幕", "中文配音", "同人作品", "断面图", "ASMR", "1080p", "60FPS"]
        self.properties_checkboxes = {}
        for i, prop in enumerate(properties_options):
            checkbox = QCheckBox(prop)
            if prop in self.filters.get('properties', []):
                checkbox.setChecked(True)
            self.properties_checkboxes[prop] = checkbox
            properties_layout.addWidget(checkbox, i // 3, i % 3)
        scroll_layout.addWidget(properties_group)
        
        relationship_group = QGroupBox("人物关系")
        relationship_layout = QGridLayout(relationship_group)
        relationship_options = ["近亲", "姐", "妹", "母", "女儿", "师生", "情侣", "青梅竹马", "同事"]
        self.relationship_checkboxes = {}
        for i, rel in enumerate(relationship_options):
            checkbox = QCheckBox(rel)
            if rel in self.filters.get('relationship', []):
                checkbox.setChecked(True)
            self.relationship_checkboxes[rel] = checkbox
            relationship_layout.addWidget(checkbox, i // 3, i % 3)
        scroll_layout.addWidget(relationship_group)
        
        character_group = QGroupBox("角色设定")
        character_layout = QGridLayout(character_group)
        character_options = ["JK", "处女", "御姐", "熟女", "人妻", "女教师", "男教师", "女医生", "女病人", "护士",
                           "OL", "女警", "大小姐", "偶像", "女仆", "巫女", "魔女", "修女", "风俗娘", "公主",
                           "女忍者", "女战士", "女骑士", "魔法少女", "异种族", "天使", "妖精", "魔物娘", "魅魔", "吸血鬼",
                           "女鬼", "兽娘", "乳牛", "机械娘", "碧池", "痴女", "雌小鬼", "不良少女", "傲娇", "病娇",
                           "无口", "无表情", "眼神死", "正太", "伪娘", "扶他"]
        self.character_checkboxes = {}
        for i, char in enumerate(character_options):
            checkbox = QCheckBox(char)
            if char in self.filters.get('character_setting', []):
                checkbox.setChecked(True)
            self.character_checkboxes[char] = checkbox
            character_layout.addWidget(checkbox, i // 3, i % 3)
        scroll_layout.addWidget(character_group)
        
        appearance_group = QGroupBox("外貌身材")
        appearance_layout = QGridLayout(appearance_group)
        appearance_options = ["短发", "马尾", "双马尾", "丸子头", "巨乳", "乳环", "舌环", "贫乳", "黑皮肤", "晒痕",
                           "眼镜娘", "兽耳", "尖耳朵", "异色瞳", "美人痣", "肌肉女", "白虎", "阴毛", "腋毛", "大屌",
                           "着衣", "水手服", "体操服", "泳装", "比基尼", "死库水", "和服", "兔女郎", "围裙", "啦啦队",
                           "丝袜", "吊袜带", "热裤", "迷你裙", "性感内衣", "紧身衣", "丁字裤", "高跟鞋", "睡衣", "婚纱",
                           "旗袍", "古装", "哥德", "口罩", "刺青", "淫纹", "身体写字"]
        self.appearance_checkboxes = {}
        for i, app in enumerate(appearance_options):
            checkbox = QCheckBox(app)
            if app in self.filters.get('appearance_body', []):
                checkbox.setChecked(True)
            self.appearance_checkboxes[app] = checkbox
            appearance_layout.addWidget(checkbox, i // 3, i % 3)
        scroll_layout.addWidget(appearance_group)
        
        scene_group = QGroupBox("情境场所")
        scene_layout = QGridLayout(scene_group)
        scene_options = ["校园", "教室", "图书馆", "保健室", "游泳池", "爱情宾馆", "医院", "办公室", "浴室", "窗边",
                       "公共厕所", "公众场合", "户外野战", "电车", "车震", "游艇", "露营帐篷", "电影院", "健身房", "沙滩",
                       "温泉", "夜店", "监狱", "教堂"]
        self.scene_checkboxes = {}
        for i, scene in enumerate(scene_options):
            checkbox = QCheckBox(scene)
            if scene in self.filters.get('scene_location', []):
                checkbox.setChecked(True)
            self.scene_checkboxes[scene] = checkbox
            scene_layout.addWidget(checkbox, i // 3, i % 3)
        scroll_layout.addWidget(scene_group)
        
        story_group = QGroupBox("故事剧情")
        story_layout = QGridLayout(story_group)
        story_options = ["纯爱", "恋爱喜剧", "后宫", "十指紧扣", "开大车", "NTR", "精神控制", "药物", "痴汉", "阿嘿颜",
                       "精神崩溃", "猎奇", "BDSM", "捆绑", "眼罩", "项圈", "调教", "异物插入", "寻欢洞", "肉便器",
                       "性奴隶", "胃凸", "强制", "轮奸", "凌辱", "性暴力", "逆强制", "女王样", "榨精", "母女丼",
                       "姐妹丼", "出轨", "醉酒", "摄影", "睡眠奸", "机械奸", "虫奸", "性转换", "百合", "耽美",
                       "时间停止", "异世界", "怪兽", "哥布林", "世界末日"]
        self.story_checkboxes = {}
        for i, story in enumerate(story_options):
            checkbox = QCheckBox(story)
            if story in self.filters.get('story_plot', []):
                checkbox.setChecked(True)
            self.story_checkboxes[story] = checkbox
            story_layout.addWidget(checkbox, i // 3, i % 3)
        scroll_layout.addWidget(story_group)
        
        position_group = QGroupBox("性交体位")
        position_layout = QGridLayout(position_group)
        position_options = ["手交", "指交", "乳交", "乳头交", "肛交", "双洞齐下", "脚交", "素股", "拳交", "3P",
                           "群交", "口交", "深喉咙", "口爆", "吞精", "舔蛋蛋", "舔穴", "69", "自慰", "腋交",
                           "舔腋下", "发交", "舔耳朵", "舔脚", "内射", "外射", "颜射", "潮吹", "怀孕", "喷奶",
                           "放尿", "排便", "骑乘位", "背后位", "颜面骑乘", "火车便当", "一字马", "性玩具", "飞机杯", "跳蛋",
                           "毒龙钻", "触手", "兽交", "颈手枷", "扯头发", "掐脖子", "打屁股", "肉棒打脸", "阴道外翻", "男乳首责",
                           "接吻", "舌吻", "POV"]
        self.position_checkboxes = {}
        for i, pos in enumerate(position_options):
            checkbox = QCheckBox(pos)
            if pos in self.filters.get('sexual_position', []):
                checkbox.setChecked(True)
            self.position_checkboxes[pos] = checkbox
            position_layout.addWidget(checkbox, i // 3, i % 3)
        scroll_layout.addWidget(position_group)
        
        sort_group = QGroupBox("排序方式")
        sort_layout = QGridLayout(sort_group)
        sort_options = ["最新上市", "最新上传", "本日排行", "本周排行", "本月排行", "观看次数", "点赞比例", "时长最长", "他们在看"]
        self.sort_buttons = []
        for i, sort in enumerate(sort_options):
            radio_button = QRadioButton(sort)
            if sort == self.filters.get('sort', '最新上市'):
                radio_button.setChecked(True)
            self.sort_buttons.append((sort, radio_button))
            sort_layout.addWidget(radio_button, i // 2, i % 2)
        scroll_layout.addWidget(sort_group)
        
        date_group = QGroupBox("发布日期")
        date_layout = QGridLayout(date_group)
        date_options = ["全部", "过去 24 小时", "过去 2 天", "过去 1 周", "过去 1 个月", "过去 3 个月", "过去 1 年"]
        self.date_buttons = []
        for i, date in enumerate(date_options):
            radio_button = QRadioButton(date)
            if date == self.filters.get('date', '全部'):
                radio_button.setChecked(True)
            self.date_buttons.append((date, radio_button))
            date_layout.addWidget(radio_button, i // 2, i % 2)
        scroll_layout.addWidget(date_group)
        
        duration_group = QGroupBox("时长")
        duration_layout = QGridLayout(duration_group)
        duration_options = ["全部", "1 分钟 +", "5 分钟 +", "10 分钟 +", "20 分钟 +", "30 分钟 +", "60 分钟 +", "0 - 10 分钟", "0 - 20 分钟"]
        self.duration_buttons = []
        for i, duration in enumerate(duration_options):
            radio_button = QRadioButton(duration)
            if duration == self.filters.get('duration', '全部'):
                radio_button.setChecked(True)
            self.duration_buttons.append((duration, radio_button))
            duration_layout.addWidget(radio_button, i // 3, i % 3)
        scroll_layout.addWidget(duration_group)
        
        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("应用筛选")
        self.save_button.clicked.connect(self.save_filters)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def save_filters(self):
        try:
            self.filters['keyword'] = self.keyword_input.text().strip()
            for genre, button in self.genre_buttons:
                if button.isChecked():
                    self.filters['genre'] = genre
                    break
            self.filters['properties'] = []
            for prop, checkbox in self.properties_checkboxes.items():
                if checkbox.isChecked():
                    self.filters['properties'].append(prop)
            self.filters['relationship'] = []
            for rel, checkbox in self.relationship_checkboxes.items():
                if checkbox.isChecked():
                    self.filters['relationship'].append(rel)
            self.filters['character_setting'] = []
            for char, checkbox in self.character_checkboxes.items():
                if checkbox.isChecked():
                    self.filters['character_setting'].append(char)
            self.filters['appearance_body'] = []
            for app, checkbox in self.appearance_checkboxes.items():
                if checkbox.isChecked():
                    self.filters['appearance_body'].append(app)
            self.filters['scene_location'] = []
            for scene, checkbox in self.scene_checkboxes.items():
                if checkbox.isChecked():
                    self.filters['scene_location'].append(scene)
            self.filters['story_plot'] = []
            for story, checkbox in self.story_checkboxes.items():
                if checkbox.isChecked():
                    self.filters['story_plot'].append(story)
            self.filters['sexual_position'] = []
            for pos, checkbox in self.position_checkboxes.items():
                if checkbox.isChecked():
                    self.filters['sexual_position'].append(pos)
            for sort, button in self.sort_buttons:
                if button.isChecked():
                    self.filters['sort'] = sort
                    break
            for date, button in self.date_buttons:
                if button.isChecked():
                    self.filters['date'] = date
                    break
            for duration, button in self.duration_buttons:
                if button.isChecked():
                    self.filters['duration'] = duration
                    break
            self.accept()
        except Exception as e:
            print(f"保存筛选条件失败: {e}")
    
    def get_filters(self):
        return self.filters

class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setGeometry(100, 100, 400, 250)
        self.settings = settings or {
            'download_mode': 'multi_thread',
            'num_threads': 4
        }
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        download_mode_group = QGroupBox("下载方式")
        download_mode_layout = QVBoxLayout()
        self.multi_thread_radio = QRadioButton("多线程下载")
        self.single_thread_radio = QRadioButton("单线程下载")
        if self.settings['download_mode'] == 'multi_thread':
            self.multi_thread_radio.setChecked(True)
        else:
            self.single_thread_radio.setChecked(True)
        download_mode_layout.addWidget(self.multi_thread_radio)
        download_mode_layout.addWidget(self.single_thread_radio)
        download_mode_group.setLayout(download_mode_layout)
        layout.addWidget(download_mode_group)
        
        threads_group = QGroupBox("线程数设置")
        threads_layout = QVBoxLayout()
        threads_layout.addWidget(QLabel("线程数量:"))
        self.threads_spinbox = QSpinBox()
        self.threads_spinbox.setMinimum(1)
        self.threads_spinbox.setMaximum(16)
        self.threads_spinbox.setValue(self.settings['num_threads'])
        threads_layout.addWidget(self.threads_spinbox)
        threads_group.setLayout(threads_layout)
        layout.addWidget(threads_group)
        
        self.multi_thread_radio.toggled.connect(self.on_download_mode_changed)
        self.single_thread_radio.toggled.connect(self.on_download_mode_changed)
        self.on_download_mode_changed()
        
        button_layout = QHBoxLayout()
        self.save_button = QPushButton("保存")
        self.save_button.clicked.connect(self.save_settings)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def on_download_mode_changed(self):
        self.threads_spinbox.setEnabled(self.multi_thread_radio.isChecked())
    
    def load_settings(self):
        try:
            import json
            import os
            if os.path.exists('settings.json'):
                with open('settings.json', 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
        except Exception:
            self.settings = {'download_mode': 'multi_thread', 'num_threads': 4}
    
    def save_settings(self):
        try:
            self.settings['download_mode'] = 'multi_thread' if self.multi_thread_radio.isChecked() else 'single_thread'
            self.settings['num_threads'] = self.threads_spinbox.value()
            import json
            with open('settings.json', 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
            self.accept()
        except Exception as e:
            print(f"保存设置失败: {e}")
    
    def get_settings(self):
        return self.settings

class Hanime1GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api = Hanime1API()
        self.current_search_results = []
        self.current_video_info = None
        self.favorites = []
        self.favorites_file = "hanime1_favorites.json"
        self.load_favorites()
        self.settings = {'download_mode': 'multi_thread', 'num_threads': 4}
        self.load_settings()
        self.filters = {
            'keyword': '',
            'genre': '全部',
            'sort': '最新上市',
            'date': '全部',
            'duration': '全部',
            'properties': [],
            'relationship': [],
            'character_setting': [],
            'appearance_body': [],
            'scene_location': [],
            'story_plot': [],
            'sexual_position': []
        }
        self.threadpool = QThreadPool()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Hanime1视频工具")
        self.setGeometry(100, 100, 1200, 800)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        left_widget = QWidget()
        left_widget.setMinimumWidth(350)
        left_widget.setMaximumWidth(500)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(12)
        
        search_title = QLabel("视频搜索")
        left_layout.addWidget(search_title)
        
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("请输入搜索关键词...")
        search_layout.addWidget(self.search_input, 1)
        self.filter_button = QPushButton("筛选")
        self.filter_button.clicked.connect(self.show_filter_dialog)
        search_layout.addWidget(self.filter_button)
        self.search_button = QPushButton("搜索")
        self.search_button.clicked.connect(self.search_videos)
        search_layout.addWidget(self.search_button)
        left_layout.addLayout(search_layout)
        
        page_layout = QHBoxLayout()
        page_layout.addWidget(QLabel("页码:"))
        self.page_spinbox = QSpinBox()
        self.page_spinbox.setMinimum(1)
        self.page_spinbox.setMaximum(100)
        page_layout.addWidget(self.page_spinbox)
        left_layout.addLayout(page_layout)
        
        self.batch_download_button = QPushButton("批量下载搜索结果")
        self.batch_download_button.clicked.connect(self.on_batch_download)
        left_layout.addWidget(self.batch_download_button)
        
        self.settings_button = QPushButton("设置")
        self.settings_button.clicked.connect(self.show_settings)
        left_layout.addWidget(self.settings_button)
        
        from PyQt5.QtWidgets import QCheckBox
        self.proxy_checkbox = QCheckBox("启用代理")
        self.proxy_checkbox.setChecked(False)
        self.proxy_checkbox.stateChanged.connect(self.on_proxy_toggled)
        left_layout.addWidget(self.proxy_checkbox)
        
        from PyQt5.QtWidgets import QTabWidget
        tab_widget = QTabWidget()
        self.video_list = QListWidget()
        self.video_list.itemClicked.connect(self.on_video_selected)
        self.video_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.video_list.customContextMenuRequested.connect(self.show_video_context_menu)
        tab_widget.addTab(self.video_list, "搜索结果")
        self.favorites_list = QListWidget()
        self.favorites_list.itemClicked.connect(self.on_favorite_selected)
        self.favorites_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.favorites_list.customContextMenuRequested.connect(self.show_favorite_context_menu)
        tab_widget.addTab(self.favorites_list, "收藏夹")
        self.update_favorites_list()
        left_layout.addWidget(tab_widget)
        main_layout.addWidget(left_widget)
        
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(16)
        
        info_group = QGroupBox("视频信息")
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(8)
        self.info_form = QFormLayout()
        self.info_form.setSpacing(5)
        self.info_form.setVerticalSpacing(8)
        self.title_label = QLabel("-")
        self.title_label.setWordWrap(True)
        self.chinese_title_label = QLabel("-")
        self.chinese_title_label.setWordWrap(True)
        self.views_label = QLabel("-")
        self.upload_date_label = QLabel("-")
        self.likes_label = QLabel("-")
        self.tags_label = QLabel("-")
        self.tags_label.setWordWrap(True)
        self.description_text = QTextEdit("-")
        self.description_text.setReadOnly(True)
        self.description_text.setMaximumHeight(120)
        self.view_cover_button = QPushButton("查看封面")
        self.view_cover_button.clicked.connect(self.show_cover)
        self.view_cover_button.setEnabled(False)
        self.current_cover_url = ""
        self.info_form.addRow(QLabel("标题:"), self.title_label)
        self.info_form.addRow(QLabel("中文标题:"), self.chinese_title_label)
        self.info_form.addRow(QLabel("观看次数:"), self.views_label)
        self.info_form.addRow(QLabel("上传日期:"), self.upload_date_label)
        self.info_form.addRow(QLabel("点赞:"), self.likes_label)
        self.info_form.addRow(QLabel("标签:"), self.tags_label)
        self.info_form.addRow(QLabel("封面:"), self.view_cover_button)
        self.info_form.addRow(QLabel("描述:"), self.description_text)
        info_layout.addLayout(self.info_form)
        
        related_group = QGroupBox("相关视频")
        related_layout = QVBoxLayout(related_group)
        related_layout.setSpacing(5)
        self.related_list = QListWidget()
        self.related_list.setMinimumHeight(150)
        self.related_list.setMaximumHeight(200)
        self.related_list.itemClicked.connect(self.on_related_video_clicked)
        related_layout.addWidget(self.related_list)
        info_layout.addWidget(related_group)
        
        source_links_title = QLabel("当前视频源链接:")
        info_layout.addWidget(source_links_title)
        self.source_links_widget = QWidget()
        self.source_links_widget.setMinimumHeight(150)
        self.source_links_widget.setMaximumHeight(250)
        self.source_links_layout = QVBoxLayout(self.source_links_widget)
        self.source_links_layout.setSpacing(8)
        self.source_links_layout.setContentsMargins(10, 5, 10, 5)
        info_layout.addWidget(self.source_links_widget)
        right_layout.addWidget(info_group)
        
        download_group = QGroupBox("下载管理")
        download_layout = QVBoxLayout(download_group)
        download_layout.setSpacing(8)
        self.download_list = QListWidget()
        self.download_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.download_list.customContextMenuRequested.connect(self.show_download_context_menu)
        download_layout.addWidget(QLabel("下载队列:"))
        download_layout.addWidget(self.download_list)
        
        download_control_layout = QHBoxLayout()
        download_control_layout.setSpacing(5)
        self.start_download_button = QPushButton("开始下载")
        self.start_download_button.clicked.connect(self.on_start_download)
        self.pause_download_button = QPushButton("暂停下载")
        self.pause_download_button.clicked.connect(self.on_pause_download)
        self.cancel_download_button = QPushButton("取消下载")
        self.cancel_download_button.clicked.connect(self.on_cancel_download)
        self.clear_download_button = QPushButton("清空列表")
        self.clear_download_button.clicked.connect(self.on_clear_download_list)
        download_control_layout.addWidget(self.start_download_button)
        download_control_layout.addWidget(self.pause_download_button)
        download_control_layout.addWidget(self.cancel_download_button)
        download_control_layout.addWidget(self.clear_download_button)
        download_layout.addLayout(download_control_layout)
        
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(5)
        self.download_progress = QProgressBar()
        self.download_progress.setValue(0)
        self.download_info = QLabel("准备下载")
        progress_layout.addWidget(QLabel("下载进度:"))
        progress_layout.addWidget(self.download_progress)
        progress_layout.addWidget(self.download_info)
        download_layout.addLayout(progress_layout)
        right_layout.addWidget(download_group)
        main_layout.addWidget(right_widget)
        
        self.statusBar()
        self.downloads = []
        self.active_downloads = {}
    
    def search_videos(self):
        keyword = self.search_input.text().strip()
        self.filters['keyword'] = keyword
        self.statusBar().showMessage(f"正在搜索: {keyword}...")
        
        genre = self.filters['genre'] if self.filters['genre'] != '全部' else ""
        sort = self.filters['sort'] if self.filters['sort'] != '最新上市' else ""
        date = self.filters['date'] if self.filters['date'] != '全部' else ""
        duration = self.filters['duration'] if self.filters['duration'] != '全部' else ""
        page = self.page_spinbox.value()
        
        worker = SearchWorker(
            api=self.api,
            query=keyword,
            genre=genre,
            sort=sort,
            date=date,
            duration=duration,
            page=page
        )
        worker.signals.result.connect(self.on_search_complete)
        worker.signals.error.connect(self.on_search_error)
        worker.signals.finished.connect(self.on_search_finished)
        self.threadpool.start(worker)
    
    def on_search_complete(self, search_result):
        if search_result and search_result['videos']:
            original_videos = search_result['videos']
            filtered_videos = self.apply_client_filters(original_videos)
            self.current_search_results = filtered_videos
            self.video_list.clear()
            for video in filtered_videos:
                self.video_list.addItem(f"[{video['video_id']}] {video['title']}")
            self.statusBar().showMessage(f"搜索完成，找到 {len(filtered_videos)} 个结果")
        else:
            self.video_list.clear()
            self.statusBar().showMessage("未找到视频结果")
    
    def apply_client_filters(self, videos):
        has_detailed_filters = any(
            self.filters.get(key, [])
            for key in ['properties', 'relationship', 'character_setting', 
                       'appearance_body', 'scene_location', 'story_plot', 'sexual_position']
        )
        
        if not has_detailed_filters:
            return videos
        
        filtered_videos = []
        for video in videos:
            try:
                video_info = self.api.get_video_info(video['video_id'])
                if not video_info:
                    continue
                
                matches = True
                all_filter_tags = set()
                all_filter_tags.update(self.filters.get('properties', []))
                all_filter_tags.update(self.filters.get('relationship', []))
                all_filter_tags.update(self.filters.get('character_setting', []))
                all_filter_tags.update(self.filters.get('appearance_body', []))
                all_filter_tags.update(self.filters.get('scene_location', []))
                all_filter_tags.update(self.filters.get('story_plot', []))
                all_filter_tags.update(self.filters.get('sexual_position', []))
                
                video_tags = set(video_info.get('tags', []))
                if not all_filter_tags.issubset(video_tags):
                    matches = False
                
                if matches:
                    filtered_videos.append(video)
            except Exception:
                continue
        return filtered_videos
    
    def on_search_error(self, error):
        self.statusBar().showMessage(f"搜索出错: {error}")
    
    def on_search_finished(self):
        pass
    
    def on_video_selected(self, item):
        index = self.video_list.row(item)
        if 0 <= index < len(self.current_search_results):
            video = self.current_search_results[index]
            self.get_video_info(video['video_id'])
    
    def get_video_info(self, video_id):
        self.statusBar().showMessage(f"正在获取视频 {video_id} 的信息...")
        worker = GetVideoInfoWorker(api=self.api, video_id=video_id)
        worker.signals.result.connect(lambda result: self.on_video_info_complete(result, video_id))
        worker.signals.error.connect(lambda error: self.on_video_info_error(error, video_id))
        worker.signals.finished.connect(self.on_video_info_finished)
        self.threadpool.start(worker)
    
    def show_cover(self):
        if self.current_cover_url:
            try:
                from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
                from PyQt5.QtCore import Qt
                from PyQt5.QtGui import QPixmap
                import requests
                
                dialog = QDialog(self)
                dialog.setWindowTitle("视频封面")
                dialog.setGeometry(100, 100, 800, 600)
                layout = QVBoxLayout(dialog)
                cover_label = QLabel()
                cover_label.setAlignment(Qt.AlignCenter)
                proxies = self.api.session.proxies if self.api.is_proxy_enabled() else None
                response = requests.get(self.current_cover_url, proxies=proxies, timeout=10)
                response.raise_for_status()
                pixmap = QPixmap()
                pixmap.loadFromData(response.content)
                scaled_pixmap = pixmap.scaled(780, 540, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                cover_label.setPixmap(scaled_pixmap)
                close_button = QPushButton("关闭")
                close_button.clicked.connect(dialog.close)
                layout.addWidget(cover_label)
                layout.addWidget(close_button)
                dialog.exec_()
            except Exception as e:
                self.statusBar().showMessage(f"显示封面失败: {str(e)}")
        else:
            self.statusBar().showMessage("没有可用的封面")
    
    def on_video_info_complete(self, video_info, video_id):
        if video_info:
            self.current_video_info = video_info
            self.title_label.setText(video_info['title'])
            self.chinese_title_label.setText(video_info['chinese_title'])
            self.views_label.setText(video_info['views'])
            self.upload_date_label.setText(video_info['upload_date'])
            self.likes_label.setText(video_info['likes'])
            self.tags_label.setText(", ".join(video_info['tags']))
            self.description_text.setText(video_info['description'])
            
            if 'thumbnail' in video_info and video_info['thumbnail']:
                self.current_cover_url = video_info['thumbnail']
                self.view_cover_button.setEnabled(True)
            else:
                self.current_cover_url = ""
                self.view_cover_button.setEnabled(False)
            
            self.related_list.clear()
            for i, related in enumerate(video_info['series']):
                video_id = related.get('video_id', '')
                title = related.get('chinese_title')
                if not title or title.strip() == '' or title == f"相关视频 {video_id}":
                    title = related.get('title')
                if not title or title.strip() == '' or title == f"相关视频 {video_id}":
                    title = f"视频 {video_id}"
                self.related_list.addItem(f"[{video_id}] {title}")
            
            self.update_source_links(video_info['video_sources'])
            self.statusBar().showMessage(f"视频 {video_id} 信息加载完成")
        else:
            self.statusBar().showMessage(f"无法获取视频 {video_id} 的信息")
            self.update_source_links([])
    
    def on_video_info_error(self, error, video_id):
        self.statusBar().showMessage(f"获取视频 {video_id} 信息出错: {error}")
    
    def on_video_info_finished(self):
        pass
    
    def load_favorites(self):
        import os
        if os.path.exists(self.favorites_file):
            try:
                import json
                with open(self.favorites_file, 'r', encoding='utf-8') as f:
                    self.favorites = json.load(f)
            except Exception:
                self.favorites = []
        else:
            self.favorites = []
    
    def save_favorites(self):
        try:
            import json
            with open(self.favorites_file, 'w', encoding='utf-8') as f:
                json.dump(self.favorites, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def load_settings(self):
        try:
            import json
            import os
            if os.path.exists('settings.json'):
                with open('settings.json', 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
            else:
                self.save_settings()
        except Exception:
            self.settings = {'download_mode': 'multi_thread', 'num_threads': 4}
    
    def save_settings(self):
        try:
            import json
            with open('settings.json', 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def show_settings(self):
        dialog = SettingsDialog(self, self.settings)
        dialog.exec_()
        self.load_settings()
    
    def show_filter_dialog(self):
        self.filters['keyword'] = self.search_input.text().strip()
        dialog = FilterDialog(self, self.filters)
        result = dialog.exec_()
        if result == QDialog.Accepted:
            self.filters = dialog.get_filters()
            self.search_input.setText(self.filters['keyword'])
            self.statusBar().showMessage(f"筛选条件已更新，正在搜索...")
            self.search_videos()
    
    def add_to_favorites(self, video):
        for fav in self.favorites:
            if fav['video_id'] == video['video_id']:
                self.statusBar().showMessage(f"视频 {video['title'][:20]}... 已在收藏夹中")
                return False
        
        self.favorites.append(video)
        self.save_favorites()
        self.statusBar().showMessage(f"成功将视频 {video['title'][:20]}... 添加到收藏夹")
        if hasattr(self, 'favorites_list'):
            self.update_favorites_list()
        return True
    
    def remove_from_favorites(self, video_id):
        for i, fav in enumerate(self.favorites):
            if fav['video_id'] == video_id:
                removed_video = self.favorites.pop(i)
                self.save_favorites()
                self.statusBar().showMessage(f"成功将视频 {removed_video['title'][:20]}... 从收藏夹中移除")
                if hasattr(self, 'favorites_list'):
                    self.update_favorites_list()
                return True
        self.statusBar().showMessage(f"视频不在收藏夹中")
        return False
    
    def is_favorite(self, video_id):
        for fav in self.favorites:
            if fav['video_id'] == video_id:
                return True
        return False
    
    def update_favorites_list(self):
        self.favorites_list.clear()
        for video in self.favorites:
            self.favorites_list.addItem(f"[{video['video_id']}] {video['title']}")
    
    def on_favorite_selected(self, item):
        text = item.text()
        import re
        match = re.search(r'\[(\d+)\]', text)
        if match:
            video_id = match.group(1)
            self.get_video_info(video_id)
    
    def show_video_context_menu(self, position):
        item = self.video_list.itemAt(position)
        if not item:
            return
        menu = QMenu()
        add_to_favorites_action = QAction("添加到收藏夹", self)
        add_to_favorites_action.triggered.connect(lambda: self.on_add_to_favorites_from_menu(item))
        menu.addAction(add_to_favorites_action)
        open_browser_action = QAction("用浏览器打开", self)
        open_browser_action.triggered.connect(lambda: self.on_open_video_in_browser(item))
        menu.addAction(open_browser_action)
        menu.exec_(self.video_list.viewport().mapToGlobal(position))
    
    def show_favorite_context_menu(self, position):
        item = self.favorites_list.itemAt(position)
        if not item:
            return
        menu = QMenu()
        view_details_action = QAction("查看详情", self)
        view_details_action.triggered.connect(lambda: self.on_favorite_selected(item))
        menu.addAction(view_details_action)
        remove_from_favorites_action = QAction("从收藏夹移除", self)
        remove_from_favorites_action.triggered.connect(lambda: self.on_remove_from_favorites_from_menu(item))
        menu.addAction(remove_from_favorites_action)
        open_browser_action = QAction("用浏览器打开", self)
        open_browser_action.triggered.connect(lambda: self.on_open_video_in_browser(item))
        menu.addAction(open_browser_action)
        menu.exec_(self.favorites_list.viewport().mapToGlobal(position))
    
    def on_add_to_favorites_from_menu(self, item):
        text = item.text()
        import re
        match = re.search(r'\[(\d+)\]', text)
        if match:
            video_id = match.group(1)
            for video in self.current_search_results:
                if video['video_id'] == video_id:
                    self.add_to_favorites(video)
                    break
    
    def on_open_video_in_browser(self, item):
        text = item.text()
        import re
        match = re.search(r'\[(\d+)\]', text)
        if match:
            video_id = match.group(1)
            video_url = f"https://hanime1.me/watch?v={video_id}"
            import webbrowser
            try:
                webbrowser.open(video_url)
                self.statusBar().showMessage(f"已在浏览器中打开视频页面")
            except Exception as e:
                self.statusBar().showMessage(f"用浏览器打开失败: {str(e)}")
    
    def on_remove_from_favorites_from_menu(self, item):
        text = item.text()
        import re
        match = re.search(r'\[(\d+)\]', text)
        if match:
            video_id = match.group(1)
            self.remove_from_favorites(video_id)
    
    def add_to_download_queue(self, video):
        worker = GetVideoInfoWorker(self.api, video['video_id'])
        worker.signals.result.connect(lambda result: self.on_video_info_for_download(result, video))
        worker.signals.error.connect(lambda error: self.on_video_info_for_download_error(error, video))
        self.threadpool.start(worker)
    
    def on_video_info_for_download(self, video_info, original_video):
        if video_info and video_info['video_sources']:
            source = video_info['video_sources'][0]
            title = video_info['chinese_title']
            if not title or title.strip() == '-':
                title = video_info['title']
            
            download_task = {
                'video_id': video_info['video_id'],
                'title': title,
                'url': source['url'],
                'status': 'pending',
                'progress': 0,
                'size': 0,
                'total_size': 0,
                'source': source
            }
            self.downloads.append(download_task)
            self.update_download_list()
            self.statusBar().showMessage(f"视频 {video_info['title'][:20]}... 已添加到下载队列")
        else:
            self.statusBar().showMessage(f"无法获取视频 {original_video['title'][:20]}... 的视频源")
    
    def on_video_info_for_download_error(self, error, video):
        self.statusBar().showMessage(f"获取视频 {video['title'][:20]}... 信息时出错: {error}")
    
    def update_download_list(self):
        self.download_list.clear()
        for download in self.downloads:
            status_text = {
                'pending': '等待中',
                'downloading': '下载中',
                'paused': '已暂停',
                'completed': '已完成',
                'error': '出错',
                'cancelled': '已取消'
            }[download['status']]
            self.download_list.addItem(f"[{download['video_id']}] {download['title'][:30]}... - {status_text} ({download['progress']:.1f}%)")
    
    def on_start_download(self):
        for i, download in enumerate(self.downloads):
            if download['status'] == 'pending' or download['status'] == 'paused':
                self.start_download(i)
                break
    
    def start_download(self, index):
        if 0 <= index < len(self.downloads):
            download = self.downloads[index]
            if download['status'] in ['pending', 'paused']:
                import re
                safe_title = download['title'][:100]
                safe_title = re.sub(r'[\\/:*?"<>|]', '_', safe_title)
                safe_title = safe_title.strip(' _')
                if not safe_title:
                    safe_title = f"video_{download['video_id']}"
                filename = f"{safe_title}.mp4"
                
                if self.settings['download_mode'] == 'multi_thread':
                    num_threads = self.settings['num_threads']
                else:
                    num_threads = 1
                
                proxy_config = self.api.session.proxies if self.api.is_proxy_enabled() else None
                worker = DownloadWorker(download['url'], filename, num_threads=num_threads, proxy_config=proxy_config)
                
                worker.signals.progress.connect(lambda progress_info, idx=index: self.on_download_progress(progress_info, idx))
                worker.signals.finished.connect(lambda idx=index: self.on_download_finished(idx))
                worker.signals.error.connect(lambda error, idx=index: self.on_download_error(error, idx))
                
                self.downloads[index]['status'] = 'downloading'
                self.downloads[index]['filename'] = filename
                self.update_download_list()
                self.active_downloads[index] = worker
                self.threadpool.start(worker)
                self.statusBar().showMessage(f"开始下载视频 {download['title'][:20]}...")
    
    def on_pause_download(self):
        for index, worker in self.active_downloads.items():
            worker.cancel()
            self.downloads[index]['status'] = 'paused'
            self.update_download_list()
            self.statusBar().showMessage(f"已暂停下载视频 {self.downloads[index]['title'][:20]}...")
            break
    
    def on_cancel_download(self):
        for index, worker in self.active_downloads.items():
            worker.cancel()
            self.downloads[index]['status'] = 'cancelled'
            self.active_downloads.pop(index)
            self.update_download_list()
            self.statusBar().showMessage(f"已取消下载视频 {self.downloads[index]['title'][:20]}...")
            break
    
    def on_clear_download_list(self):
        for worker in self.active_downloads.values():
            worker.cancel()
        self.downloads.clear()
        self.active_downloads.clear()
        self.update_download_list()
        self.download_progress.setValue(0)
        self.download_info.setText("准备下载")
        self.statusBar().showMessage("已清空下载列表")
    
    def on_download_progress(self, progress_info, index):
        if 0 <= index < len(self.downloads):
            self.downloads[index]['progress'] = progress_info['progress']
            self.downloads[index]['size'] = progress_info['size']
            self.downloads[index]['total_size'] = progress_info['total_size']
            self.update_download_list()
            self.download_progress.setValue(int(progress_info['progress']))
            total_size_mb = progress_info['total_size'] / (1024 * 1024)
            downloaded_size_mb = progress_info['size'] / (1024 * 1024)
            self.download_info.setText(f"正在下载: {progress_info['filename'][:30]}... {downloaded_size_mb:.1f}MB / {total_size_mb:.1f}MB")
    
    def on_download_finished(self, index):
        if 0 <= index < len(self.downloads):
            self.downloads[index]['status'] = 'completed'
            self.downloads[index]['progress'] = 100.0
            if index in self.active_downloads:
                self.active_downloads.pop(index)
            self.update_download_list()
            self.statusBar().showMessage(f"视频 {self.downloads[index]['title'][:20]}... 下载完成")
            self.on_start_download()
    
    def on_download_error(self, error, index):
        if 0 <= index < len(self.downloads):
            self.downloads[index]['status'] = 'error'
            if index in self.active_downloads:
                self.active_downloads.pop(index)
            self.update_download_list()
            self.statusBar().showMessage(f"视频 {self.downloads[index]['title'][:20]}... 下载出错: {error}")
            self.on_start_download()
    
    def on_batch_download(self):
        if not self.current_search_results:
            self.statusBar().showMessage("搜索结果为空，无法批量下载")
            return
        self.statusBar().showMessage(f"开始添加 {len(self.current_search_results)} 个视频到下载队列...")
        for video in self.current_search_results:
            self.add_to_download_queue(video)
    
    def show_download_context_menu(self, position):
        item = self.download_list.itemAt(position)
        if not item:
            return
        menu = QMenu()
        start_action = QAction("开始下载", self)
        start_action.triggered.connect(lambda: self.on_start_download_from_menu(item))
        menu.addAction(start_action)
        pause_action = QAction("暂停下载", self)
        pause_action.triggered.connect(lambda: self.on_pause_download_from_menu(item))
        menu.addAction(pause_action)
        cancel_action = QAction("取消下载", self)
        cancel_action.triggered.connect(lambda: self.on_cancel_download_from_menu(item))
        menu.addAction(cancel_action)
        remove_action = QAction("从队列中移除", self)
        remove_action.triggered.connect(lambda: self.on_remove_from_download_queue(item))
        menu.addAction(remove_action)
        menu.exec_(self.download_list.viewport().mapToGlobal(position))
    
    def on_start_download_from_menu(self, item):
        index = self.download_list.row(item)
        self.start_download(index)
    
    def on_pause_download_from_menu(self, item):
        index = self.download_list.row(item)
        if 0 <= index < len(self.downloads) and index in self.active_downloads:
            self.active_downloads[index].cancel()
            self.downloads[index]['status'] = 'paused'
            self.update_download_list()
            self.statusBar().showMessage(f"已暂停下载视频 {self.downloads[index]['title'][:20]}...")
    
    def on_cancel_download_from_menu(self, item):
        index = self.download_list.row(item)
        if 0 <= index < len(self.downloads) and index in self.active_downloads:
            self.active_downloads[index].cancel()
            self.downloads[index]['status'] = 'cancelled'
            self.active_downloads.pop(index)
            self.update_download_list()
            self.statusBar().showMessage(f"已取消下载视频 {self.downloads[index]['title'][:20]}...")
    
    def on_remove_from_download_queue(self, item):
        index = self.download_list.row(item)
        if 0 <= index < len(self.downloads):
            if index in self.active_downloads:
                self.active_downloads[index].cancel()
                self.active_downloads.pop(index)
            removed_download = self.downloads.pop(index)
            self.update_download_list()
            self.statusBar().showMessage(f"已从下载队列中移除视频 {removed_download['title'][:20]}...")
    
    def on_related_video_clicked(self, item):
        text = item.text()
        import re
        match = re.search(r'\[(\d+)\]', text)
        if match:
            video_id = match.group(1)
            self.get_video_info(video_id)
    
    def update_source_links(self, video_sources):
        while self.source_links_layout.count() > 0:
            item = self.source_links_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        if not video_sources:
            no_sources_label = QLabel("当前视频没有可用的视频源")
            self.source_links_layout.addWidget(no_sources_label)
            return
        
        tips_label = QLabel("左键点击添加/移除下载队列，右键菜单")
        self.source_links_layout.addWidget(tips_label)
        
        for i, source in enumerate(video_sources):
            quality = source['quality'] if source['quality'] != 'unknown' else f"源{i+1}"
            button_text = f"{quality} - {source['type']}"
            source_button = QPushButton(button_text)
            source_button.setToolTip(source['url'])
            source_button.setContextMenuPolicy(Qt.CustomContextMenu)
            source_button.customContextMenuRequested.connect(lambda pos, btn=source_button, url=source['url']: self.show_source_link_context_menu(pos, btn, url))
            source_button.clicked.connect(lambda checked, url=source['url'], quality=quality: self.toggle_download_queue(url, quality))
            self.source_links_layout.addWidget(source_button)
    
    def show_source_link_context_menu(self, position, button, url):
        menu = QMenu()
        copy_action = QAction("复制链接", self)
        copy_action.triggered.connect(lambda: self.copy_to_clipboard(url))
        menu.addAction(copy_action)
        download_action = QAction("下载视频", self)
        download_action.triggered.connect(lambda: self.download_from_source(url))
        menu.addAction(download_action)
        menu.exec_(button.mapToGlobal(position))
    
    def copy_to_clipboard(self, text):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self.statusBar().showMessage(f"已复制链接到剪贴板")
    
    def download_from_source(self, url):
        if not self.current_video_info:
            self.statusBar().showMessage(f"无法下载视频，当前没有视频信息")
            return
        
        try:
            import re
            quality_match = re.search(r'-(\d+p)\.', url)
            quality = quality_match.group(1) if quality_match else 'unknown'
            video_id = self.current_video_info['video_id']
            title = self.current_video_info['chinese_title']
            if not title or title.strip() == '-':
                title = self.current_video_info['title']
            
            self.statusBar().showMessage(f"正在准备下载视频: {title[:20]}...")
            download_task = {
                'video_id': video_id,
                'title': title,
                'url': url,
                'status': 'pending',
                'progress': 0,
                'size': 0,
                'total_size': 0,
                'source': {'url': url, 'quality': quality, 'type': 'mp4'}
            }
            self.downloads.append(download_task)
            self.update_download_list()
            self.statusBar().showMessage(f"视频 {title[:20]}... (清晰度: {quality}) 已添加到下载队列")
        except Exception as e:
            self.statusBar().showMessage(f"准备下载视频失败: {str(e)}")
    
    def toggle_download_queue(self, url, quality):
        if not self.current_video_info:
            self.statusBar().showMessage(f"无法下载视频，当前没有视频信息")
            return
        
        try:
            video_id = self.current_video_info['video_id']
            title = self.current_video_info['chinese_title']
            if not title or title.strip() == '-':
                title = self.current_video_info['title']
            
            existing_index = -1
            for i, task in enumerate(self.downloads):
                if task['video_id'] == video_id:
                    existing_index = i
                    break
            
            same_url_index = -1
            for i, task in enumerate(self.downloads):
                if task['url'] == url:
                    same_url_index = i
                    break
            
            if same_url_index != -1:
                self.downloads.pop(same_url_index)
                self.statusBar().showMessage(f"视频 {title[:20]}... ({quality}) 已从下载队列中移除")
            else:
                if existing_index != -1:
                    self.downloads.pop(existing_index)
                
                download_task = {
                    'video_id': video_id,
                    'title': title,
                    'url': url,
                    'status': 'pending',
                    'progress': 0,
                    'size': 0,
                    'total_size': 0,
                    'source': {'url': url, 'quality': quality, 'type': 'mp4'}
                }
                self.downloads.append(download_task)
                self.statusBar().showMessage(f"视频 {title[:20]}... ({quality}) 已添加到下载队列")
            
            self.update_download_list()
        except Exception as e:
            self.statusBar().showMessage(f"切换下载队列失败: {str(e)}")
    
    def closeEvent(self, event):
        for worker in self.active_downloads.values():
            worker.cancel()
        event.accept()
    
    def on_proxy_toggled(self, state):
        if state == Qt.Checked:
            self.api.enable_proxy()
        else:
            self.api.disable_proxy()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = Hanime1GUI()
    window.show()
    sys.exit(app.exec_())
