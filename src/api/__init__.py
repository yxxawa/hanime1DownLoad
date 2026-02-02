# 在 Hanime1API 类的 __init__ 方法开头添加
def __init__(self):
    # 处理打包后的证书路径
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包环境
        certifi_path = os.path.join(sys._MEIPASS, 'certifi', 'cacert.pem')
    elif getattr(sys, 'frozen', False):
        # Nuitka 打包环境
        certifi_path = os.path.join(os.path.dirname(sys.executable), 'certifi', 'cacert.pem')
    else:
        certifi_path = None

    if certifi_path and os.path.exists(certifi_path):
        os.environ['REQUESTS_CA_BUNDLE'] = certifi_path
        os.environ['SSL_CERT_FILE'] = certifi_path