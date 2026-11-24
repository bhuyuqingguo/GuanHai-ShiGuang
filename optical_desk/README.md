# 观海·拾光 · Windows 版

屏幕右侧的轻量光盘读写面板，面向 Windows 10 / 11 x64。

## 功能

- 光盘检测、目录浏览、搜索、打开及整盘导出。
- 文件和文件夹拖拽刻录，默认标准 CD 模式。
- 快速／深度擦除、建立 Windows 可写文件目录、弹出光盘。
- 明确进度百分比、操作取消、本机历史记录。
- 跨系统加密交接：生成离线 HTML，Windows 和麒麟接收方均可用浏览器解密并保存 ZIP。
- 多套皮肤、随机启动动画、桌面浮动图标及完整快捷键。
- 按 F1 打开九章教学，使用 Windows 本机语音离线朗读。

## 从源码运行

```powershell
python -m pip install -r requirements.txt
python main.py
```

Windows 需要系统自带 Tk 和 IMAPI2。打包使用 PyInstaller；正式构建配置位于仓库 `build/`。

## 数据与安全

操作历史、设置和 DPAPI 加密密码归档保存在当前 Windows 账户的本地目录，不上传网络。擦除和格式化不可撤销，操作前必须核对光驱并备份资料。
