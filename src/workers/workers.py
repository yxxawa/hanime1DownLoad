"""
Hanime1DL 后台任务工作线程类
"""

import concurrent.futures
import glob
import logging
import os
import shutil
import threading
import time

import requests
from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot


class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)
    progress = pyqtSignal(dict)


class SearchWorker(QRunnable):
    def __init__(self, api, query, page=1, filter_params=None):
        super().__init__()
        self.api = api
        self.query = query
        self.page = page
        self.filter_params = filter_params or {}
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            result = self.api.search_videos(
                query=self.query, page=self.page, filter_params=self.filter_params
            )
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


class GetVideoInfoWorker(QRunnable):
    def __init__(self, api, video_id, visibility_settings=None):
        super().__init__()
        self.api = api
        self.video_id = video_id
        self.visibility_settings = visibility_settings
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            result = self.api.get_video_info(self.video_id, self.visibility_settings)
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


class DownloadWorker(QRunnable):
    """下载工作线程，支持多线程和断点续传"""

    # 常量定义
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    CHUNK_SIZE = 131072  # 下载块大小128KB，减少I/O操作次数
    MIN_CHUNK_SIZE = 1024 * 1024  # 最小块大小(1MB)，小于此值使用单线程

    def __init__(
        self,
        url,
        filename,
        save_path=".",
        num_threads=4,
        headers=None,
        cookies=None,
        downloaded_size=0,
    ):
        super().__init__()
        self.url = url
        self.filename = filename
        self.save_path = save_path
        self.num_threads = num_threads
        self.headers = headers or {"User-Agent": self.USER_AGENT}
        self.cookies = cookies or {}
        self.signals = WorkerSignals()
        self.is_paused = False
        self.progress_lock = None
        self.pause_event = threading.Event()
        self.pause_event.set()  # 默认不暂停
        self.downloaded_size = downloaded_size  # 已下载的大小，用于断点续传

        # 初始化 Session
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=num_threads + 2, pool_maxsize=num_threads + 2, max_retries=0
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update(self.headers)
        if self.cookies:
            self.session.cookies.update(self.cookies)

        # 进度更新节流机制
        self.last_progress_update = 0
        self.last_progress_value = 0
        self.progress_update_interval = 0.1
        self.progress_update_threshold = 1.0

        # 下载速度计算
        self.start_time = time.time()
        self.last_speed_update = 0
        self.last_downloaded_size = 0
        self.current_speed = 0

    @pyqtSlot()
    def run(self):
        try:
            os.makedirs(self.save_path, exist_ok=True)
            self.full_path = os.path.join(self.save_path, self.filename)

            file_info = self._get_file_info()
            if not file_info:
                return

            file_total_size, supports_range_requests = file_info
            self.progress_lock = threading.Lock()
            downloaded_size = 0

            if supports_range_requests and file_total_size > 0:
                self._download_with_multithreading(file_total_size)
            else:
                self._download_with_singlethread(file_total_size)

            self.signals.progress.emit(
                {
                    "progress": 100,
                    "filename": self.filename,
                    "size": file_total_size,
                    "total_size": file_total_size,
                }
            )

            self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(str(e))

    def _get_file_info(self):
        response = self.session.head(self.url, timeout=10)
        response.raise_for_status()

        content_length = response.headers.get("content-length")
        file_total_size = int(content_length) if content_length else 0

        accept_ranges = response.headers.get("accept-ranges", "none")
        supports_range_requests = accept_ranges.lower() == "bytes" and file_total_size > 0

        return file_total_size, supports_range_requests

    def _download_with_multithreading(self, file_total_size):
        if file_total_size < 10 * 1024 * 1024:
            optimal_threads = min(self.num_threads, 2)
        elif file_total_size < 50 * 1024 * 1024:
            optimal_threads = min(self.num_threads, 4)
        elif file_total_size < 200 * 1024 * 1024:
            optimal_threads = min(self.num_threads, 8)
        else:
            optimal_threads = min(self.num_threads, 16)

        chunk_size = file_total_size // optimal_threads
        if chunk_size < self.MIN_CHUNK_SIZE:
            optimal_threads = 1
            chunk_size = file_total_size

        self.num_threads = optimal_threads

        temp_files = [f"{self.full_path}.part{i}" for i in range(self.num_threads)]
        ranges = []
        for i in range(self.num_threads):
            start = i * chunk_size
            end = start + chunk_size - 1 if i < self.num_threads - 1 else file_total_size - 1
            ranges.append((start, end))

        # 初始化已下载大小容器，优先使用传入的downloaded_size
        downloaded_size_container = [self.downloaded_size]

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            future_to_chunk = {
                executor.submit(
                    self._download_chunk, i, range_tuple, file_total_size, downloaded_size_container
                ): i
                for i, range_tuple in enumerate(ranges)
            }
            concurrent.futures.wait(future_to_chunk)



        # 合并分片文件
        try:
            self._merge_files(temp_files)
            # 确保合并后的文件存在且大小合理
            if os.path.exists(self.full_path):
                merged_size = os.path.getsize(self.full_path)
                # 允许一定的误差（1%）
                if merged_size >= file_total_size * 0.99:
                    # 清理分片文件
                    self._cleanup_temp_files(temp_files)
                    # 额外清理可能的剩余分片文件
                    self._cleanup_temp_files(
                        [f"{self.full_path}.part*" for _ in range(self.num_threads)]
                    )
                else:
                    # 合并失败，清理所有文件
                    if os.path.exists(self.full_path):
                        os.remove(self.full_path)
                    self._cleanup_temp_files(temp_files)
        except Exception as e:
            # 合并失败，清理所有文件
            if os.path.exists(self.full_path):
                os.remove(self.full_path)
            self._cleanup_temp_files(temp_files)
            raise e

        # 更新下载完成的进度
        with self.progress_lock:
            downloaded_size_container[0] = file_total_size

        # 发送最终进度更新
        self.signals.progress.emit(
            {
                "progress": 100,
                "filename": self.filename,
                "size": file_total_size,
                "total_size": file_total_size,
            }
        )

    def _download_with_singlethread(self, file_total_size):
        # 检查现有文件大小
        existing_size = 0
        if os.path.exists(self.full_path):
            existing_size = os.path.getsize(self.full_path)

        # 使用已下载的大小（优先使用实例变量downloaded_size，其次使用文件大小）
        start_pos = max(self.downloaded_size, existing_size)

        # 如果已经下载完成，直接返回
        if start_pos >= file_total_size:
            self.signals.progress.emit(
                {
                    "progress": 100,
                    "filename": self.filename,
                    "size": file_total_size,
                    "total_size": file_total_size,
                }
            )
            return

        # 设置Range请求头
        headers = {"Range": f"bytes={start_pos}-"}

        # 从已下载的位置继续下载
        current_downloaded = start_pos

        with self.session.get(self.url, headers=headers, stream=True, timeout=(5, 30)) as r:
            r.raise_for_status()
            # 使用'ab'模式打开文件，追加写入
            with open(self.full_path, "ab") as f:
                for chunk in r.iter_content(chunk_size=self.CHUNK_SIZE):
                    self.pause_event.wait()
                    if chunk:
                        f.write(chunk)
                        current_downloaded += len(chunk)
                        progress = (
                            (current_downloaded / file_total_size) * 100
                            if file_total_size > 0
                            else 0
                        )

                        current_time = time.time()
                        time_diff = current_time - self.last_speed_update
                        if time_diff >= 1.0:
                            bytes_diff = current_downloaded - self.last_downloaded_size
                            self.current_speed = bytes_diff / time_diff
                            self.last_speed_update = current_time
                            self.last_downloaded_size = current_downloaded

                        if self._should_update_progress(progress):
                            self.signals.progress.emit(
                                {
                                    "progress": progress,
                                    "filename": self.filename,
                                    "size": current_downloaded,
                                    "total_size": file_total_size,
                                    "speed": self.current_speed,
                                }
                            )

    def _download_chunk(self, index, range_tuple, file_total_size, downloaded_size_container):
        start, end = range_tuple
        temp_file_path = f"{self.full_path}.part{index}"
        downloaded_chunk_size = 0
        max_retries = 3

        # 检查现有分块文件大小
        existing_size = 0
        if os.path.exists(temp_file_path):
            existing_size = os.path.getsize(temp_file_path)

        # 计算实际的开始位置
        actual_start = start + existing_size

        # 如果已经下载完成，直接返回
        if actual_start >= end:
            with self.progress_lock:
                # 确保只添加未计算的部分
                chunk_total = end - start
                if existing_size < chunk_total:
                    downloaded_size_container[0] += chunk_total - existing_size
            return {"size": end - start}

        # 设置Range请求头
        headers = {"Range": f"bytes={actual_start}-{end}"}

        for attempt in range(max_retries):
            try:
                with self.session.get(self.url, headers=headers, stream=True, timeout=(5, 30)) as r:
                    r.raise_for_status()
                    # 使用'ab'模式打开文件，追加写入
                    with open(temp_file_path, "ab") as f:
                        for chunk in r.iter_content(chunk_size=self.CHUNK_SIZE):
                            self.pause_event.wait()
                            if chunk:
                                f.write(chunk)
                                downloaded_chunk_size += len(chunk)
                                with self.progress_lock:
                                    downloaded_size_container[0] += len(chunk)
                                    current_progress = (
                                        downloaded_size_container[0] / file_total_size
                                    ) * 100

                                    current_time = time.time()
                                    time_diff = current_time - self.last_speed_update
                                    if time_diff >= 1.0:
                                        bytes_diff = (
                                            downloaded_size_container[0] - self.last_downloaded_size
                                        )
                                        self.current_speed = bytes_diff / time_diff
                                        self.last_speed_update = current_time
                                        self.last_downloaded_size = downloaded_size_container[0]

                                    if self._should_update_progress(current_progress):
                                        self.signals.progress.emit(
                                            {
                                                "progress": current_progress,
                                                "filename": self.filename,
                                                "size": downloaded_size_container[0],
                                                "total_size": file_total_size,
                                                "speed": self.current_speed,
                                            }
                                        )
                    return {"size": downloaded_chunk_size}
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                    with self.progress_lock:
                        downloaded_size_container[0] -= downloaded_chunk_size
                    downloaded_chunk_size = 0
                    continue
                else:
                    raise e
        return {"size": downloaded_chunk_size}

    def _merge_files(self, temp_files):
        with open(self.full_path, "wb") as f:
            for temp_file in temp_files:
                with open(temp_file, "rb") as tf:
                    shutil.copyfileobj(tf, f, length=1024 * 1024)

    def _cleanup_temp_files(self, temp_files):
        for temp_file in temp_files:
            if "*" in temp_file:
                files = glob.glob(temp_file)
                for file in files:
                    self._safe_remove(file)
            else:
                self._safe_remove(temp_file)

    def _safe_remove(self, file_path):
        """安全删除文件"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logging.warning(f"Failed to remove {file_path}: {e}")

    def _should_update_progress(self, current_progress):
        current_time = time.time()
        time_passed = current_time - self.last_progress_update
        progress_changed = (
            abs(current_progress - self.last_progress_value) >= self.progress_update_threshold
        )

        if time_passed >= self.progress_update_interval or progress_changed:
            self.last_progress_update = current_time
            self.last_progress_value = current_progress
            return True
        return False

    def pause(self):
        self.is_paused = True
        self.pause_event.clear()

    def resume(self):
        self.is_paused = False
        self.pause_event.set()
