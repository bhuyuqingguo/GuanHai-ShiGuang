# 观海·拾光

观海·拾光是一款轻量光盘读取、刻录、擦除与加密交接工具。主面板固定在屏幕右侧，支持拖拽刻录、完整读取、进度显示、快捷键和本地教学。

## 目录

- `optical_desk/`：Windows 10 / 11 x64 版，当前源码版本 v0.0.6。
- `kylin_desk/`：银河麒麟 V10 / Linux 版源码，当前版本 v0.0.1，支持 AMD64 与 ARM64 分别构建。
- `build/`：Windows PyInstaller 配置和版本资源。

## Windows

安装 Python 依赖后运行：

```powershell
cd optical_desk
python -m pip install -r requirements.txt
python main.py
```

Windows 单文件构建：

```powershell
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean build/GuanHaiShiGuang.spec
```

## 银河麒麟 V10

请在相同系统版本和处理器架构的麒麟构建机上执行：

```bash
cd kylin_desk
bash build_offline.sh
```

离线 wheel 与 `xorriso` 的准备方式见 `kylin_desk/README.md` 和 `kylin_desk/DEPENDENCIES.md`。Linux 可执行文件不能由 Windows 直接交叉生成，AMD64 与 ARM64 也不能混用。

## 跨系统加密交接

交接文件采用单个离线 HTML。接收方无需安装观海·拾光，在 Windows 或麒麟浏览器中输入密码即可本机解密并保存 ZIP。算法为 PBKDF2-HMAC-SHA256 与 AES-GCM；密码仍应通过独立安全渠道传递。

## 验证边界

Windows 版已进行界面、启动、加密交接和浮动图标测试。麒麟源码具有不访问真实硬件的模拟测试，但仍需在麒麟 V10 真机上验证设备权限、桌面缩放、xorriso 兼容性以及刻录／擦除回读。

## 安全提醒

擦除、格式化和刻录会改变光盘内容。执行前请核对目标设备并备份重要资料；不要在写入过程中断电、休眠或强制结束。
