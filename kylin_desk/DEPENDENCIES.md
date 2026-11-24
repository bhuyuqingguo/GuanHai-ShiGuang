# 离线依赖清单

| 组件 | 用途 | 获取方式 |
|---|---|---|
| Python 3 + venv + pip | 构建 | 麒麟安装镜像/系统源 |
| Tk（python3-tk 对应包） | 图形界面，构建和源码运行 | 麒麟安装镜像/系统源 |
| PyInstaller 6.x wheel | onefile 打包 | `prepare_offline_deps.sh`，按架构/Python 准备 |
| tkinterdnd2 wheel（可选） | 文件拖拽 | 同上；无包可移除 |
| xorriso | 刻录/擦除/UDF/弹出 | 麒麟安装镜像/系统源，或随程序附匹配架构版本 |
| Linux udev cdrom 权限 | 访问 `/dev/sr*` | 管理员离线配置 |

PyInstaller 的 onefile 不是跨架构格式。AMD64 与 ARM64 必须分别构建。构建脚本不下载任何内容。
