<img width="1280" height="640" alt="hanime1DownLoad" src="https://github.com/user-attachments/assets/003d3091-2356-4a94-887e-d08b49354ca2" />

## 界面
<img width="2559" height="1524" alt="1" src="https://github.com/user-attachments/assets/a9f46eec-805b-4c34-a111-d6504eb52b5a" />
<img width="2559" height="1527" alt="2" src="https://github.com/user-attachments/assets/49f6469d-b063-4e5e-9e3c-396d748e0721" />


## 系统要求

- Windows 7 或更高版本

## 安装方法

### 方法一：直接使用可执行文件（推荐）

1. 从 [Releases](https://github.com/yxxawa/hanime1DownLoad/releases) 页面下载最新的 `Hanime1 DL.zip` 文件
2. 解压后运行即可使用，无需安装 Python 环境

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
3. 复制网站的 Cookie（完整cookie即可）
4. 在工具的设置窗口中，将复制的 Cookie 或 cf_clearance部分 粘贴到"Cloudflare Cookie"字段
5. 点击"保存设置"按钮

### 下载速度慢

- 尝试调整"设置"中的线程数和最大同时下载数
- 检查网络连接是否稳定
- 避开网络高峰期下载

## 开发说明

### 项目结构

```
Hanime1Download/ 
 ├── main.py              # 主入口文件 
 ├── src/                 # 源代码目录 
 │   ├── api/             # API 相关代码 
 │   │   ├── __init__.py  # 包初始化文件 
 │   │   └── hanime1_api.py  # Hanime1 API 实现 
 │   ├── constants/       # 常量定义 
 │   │   ├── __init__.py  # 包初始化文件 
 │   │   └── constants.py  # 常量定义文件 
 │   ├── dialogs/         # 对话框相关代码 
 │   │   ├── __init__.py  # 包初始化文件 
 │   │   └── dialogs.py    # 对话框实现 
 │   ├── gui/             # 主界面相关代码 
 │   │   ├── __init__.py  # 包初始化文件 
 │   │   └── gui.py        # 主界面实现 
 │   ├── utils/           # 工具函数 
 │   │   └── __init__.py  # 包初始化文件 
 │   ├── widgets/         # 自定义控件 
 │   │   ├── __init__.py  # 包初始化文件 
 │   │   └── widgets.py    # 自定义控件实现 
 │   └── workers/         # 后台工作线程 
 │       ├── __init__.py  # 包初始化文件 
 │       └── workers.py    # 工作线程实现 
 ├── assets/              # 资源文件目录 
 │   ├── close.png        # 关闭图标 
 │   └── open.png         # 打开图标 
 └── 256x256.ico          # 应用图标 
```

### 核心模块说明

- **main.py**：程序的主入口
- **src/api/hanime1_api.py**：视频、详细信息等获取的API实现
- **src/gui/gui.py**：主界面
- **src/workers/workers.py**：搜索、下载等功能
- **src/widgets/widgets.py**：自定义控件，如输入框、下载列表等
- **src/dialogs/dialogs.py**：对话框实现，如筛选对话框、设置对话框等

## 贡献指南

欢迎提交 Issue 和 Pull Request 来帮助改进这个项目。


## 免责声明

- 本工具仅用于学习和研究目的
- 请遵守相关法律法规，合理使用本工具
- 下载的视频资源版权归原作者所有，请在24小时内删除








