# Hanime1VideoTool

## 项目简介

hanime1DownLoad 是一个基于 PyQt5 开发的视频下载工具,支持搜索/下载hanime的视频

## 系统要求

- Windows 7 或更高版本

## 安装方法

### 方法一：直接使用可执行文件（推荐）

1. 从 [Releases](https://github.com/yxxawa/hanime1DownLoad/releases) 页面下载最新的 `Hanime1 DL.exe` 文件
2. 双击运行即可使用，无需安装 Python 环境

### 方法二：从源码运行

1. 安装依赖：
   ```bash
   pip install PyQt5 requests certifi beautifulsoup4 zhconv
   ```

2. 运行程序：
   ```bash
   python main.py
   ```

## 常见问题

### Cloudflare 验证拦截

如果遇到搜索失败可以尝试：

1. 打开浏览器，访问 [Hanime1 网站](https://hanime1.me)
2. 完成 Cloudflare 的人机验证
3. 复制网站的 Cookie（特别是 `cf_clearance`）
4. 在工具的设置窗口中，将复制的 Cookie 或 cf_clearance部分 粘贴到"Cloudflare Cookie"字段
5. 点击"保存设置"按钮

### 下载速度慢

- 尝试调整"设置"中的线程数和最大同时下载数
- 检查网络连接是否稳定
- 避开网络高峰期下载

## 开发说明

### 项目结构

```
Hanime1Downlaod/
├── main.py              # 主入口文件
├── src/                 # 源代码目录
│   ├── api/             # API 相关代码
│   ├── constants/       # 常量定义
│   ├── dialogs/         # 对话框相关代码
│   ├── gui/             # 主界面相关代码
│   ├── utils/           # 工具函数
│   ├── widgets/         # 自定义控件
│   └── workers/         # 后台工作线程
├── 256x256.ico          # 应用图标
└── README.md            # 项目说明文档
```

### 核心模块说明

- **main.py**：程序的主入口，负责启动应用程序，显示法律声明和远程公告
- **src/api/hanime1_api.py**：与 Hanime1 网站交互的 API 客户端，负责搜索视频、获取视频信息等
- **src/gui/gui.py**：主界面实现，包含视频搜索、详情查看、下载管理等功能
- **src/workers/workers.py**：后台工作线程，负责异步执行下载、搜索等任务
- **src/widgets/widgets.py**：自定义控件，如中文支持的输入框、下载列表等
- **src/dialogs/dialogs.py**：对话框实现，如筛选对话框、设置对话框等

## 贡献指南

欢迎提交 Issue 和 Pull Request 来帮助改进这个项目。


## 免责声明

- 本工具仅用于学习和研究目的
- 请遵守相关法律法规，合理使用本工具
- 下载的视频资源版权归原作者所有，请在24小时内删除
