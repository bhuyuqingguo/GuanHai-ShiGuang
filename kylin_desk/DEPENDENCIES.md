# 离线依赖清单

| 组件 | 用途 | 获取方式 |
|---|---|---|
| Python 3 + venv + pip | 构建 | 麒麟安装镜像/系统源 |
| Tk（python3-tk 对应包） | 图形界面，构建和源码运行 | 麒麟安装镜像/系统源 |
| PyInstaller 6.x wheel | 免安装目录打包 | `prepare_offline_deps.sh`，按架构/Python 准备 |
| tkinterdnd2 wheel（可选） | 文件拖拽 | 同上；无包可移除 |
| xorriso | 刻录、擦除、弹出 | `prepare_xorriso.sh`，按架构构建并随发布包提供 |
| Linux udev cdrom 权限 | 访问 `/dev/sr*` | 管理员离线配置 |

AMD64 与 ARM64 分别构建。`build_offline.sh` 使用已准备的依赖完成离线打包。
