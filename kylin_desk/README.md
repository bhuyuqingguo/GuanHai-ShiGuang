# 观海·拾光 0.0.2 · 银河麒麟 V10 版

屏幕右侧的轻量光盘面板，支持只读设备检测、已挂载光盘浏览和导出、ISO 9660 + Joliet/Rock Ridge 刻录及快速或完整擦除。AMD64 与 ARM64 分别构建。

## 运行环境

- 银河麒麟桌面 V10 SP1，发布包以 glibc 2.31 为兼容基线。
- 解压后保留 `GuanHaiShiGuang` 和 `runtime`，双击可执行文件。首次运行自动创建桌面快捷方式，关闭窗口时最小化到任务栏。
- `runtime` 自带 Python、Tk 和刻录、擦除及弹出所用的 `xorriso`。刻录请选 ISO/Joliet 模式。
- 可选 `tkinterdnd2` 支持拖拽；缺失时仍可通过按钮添加文件，不影响其他功能。
- Linux 通常禁止普通用户直接写 `/dev/sr*`。请由管理员按单位安全策略配置 `cdrom` 组或 udev 权限；不要使用不受控的 sudo 提权。
- 读取前由麒麟桌面挂载光盘。写入/擦除前须在文件管理器中**卸载（不是弹出）**光盘。

## 一键离线构建

在**同架构、同麒麟 V10 版本**的构建机上：

```bash
cd kylin_desk
bash build_offline.sh
```

产物位于 `dist/GuanHaiShiGuang/`。发布时将其中的 `GuanHaiShiGuang` 与 `runtime` 一起打包，并保留可执行权限。

### 准备离线依赖

`offline_wheels/amd64` 和 `offline_wheels/arm64` 默认不在仓库中。联网准备机必须和目标构建机保持同架构、同 Python 主次版本；运行：

```bash
bash prepare_offline_deps.sh
bash prepare_xorriso.sh
```

随后将整个 `kylin_desk` 复制到隔离构建机。`build_offline.sh` 使用 `pip --no-index`，不会联网。若拖拽 wheel 不可得，从 `requirements-build.txt` 删除 `tkinterdnd2` 行后重跑，其他功能不受影响。

xorriso 准备脚本需要 C 编译器、make 与 curl。打包时会将构建出的可执行文件、对应源码和许可证放进 `runtime`。

## 源码运行与测试

```bash
cd kylin_desk
python3 main.py
python3 -m unittest discover -s tests -v
```

源码运行需系统 Tk；单元测试不打开光驱，不执行 xorriso。测试使用临时文件和模拟进程，只验证命令构造、标签清理、拖放解析、依赖提示和导出逻辑。

## 行为与安全

- 设备列表只枚举 `/dev/sr*`，通过只读句柄和 `CDROM_GET_CAPABILITY`、`CDROM_DRIVE_STATUS`、`CDROMREADCAPACITY` 查询；没有 `sg_inq` 依赖。
- 写操作再次限制目标名称为 `/dev/srN`，使用参数数组而非 shell。刻录默认 `-close on`，CD 模式默认 ISO + Joliet + Rock Ridge，卷标转为可移植 ASCII。
- 擦除与 UDF 初始化有二次确认，UI 会先检查卸载状态。取消仅请求 xorriso 终止，不能假定介质恢复可用，结束后必须重新检测。
- 关闭按钮最小化到任务栏，记录页可退出。
- 操作历史在 `$XDG_DATA_HOME/GuanHaiShiGuang/history.json`，皮肤在 `$XDG_CONFIG_HOME/GuanHaiShiGuang/settings.json`。

## 尚需真机验证

自动化构建在相同 glibc 基线的 Linux 环境验证启动、快捷方式、任务栏和 ISO 生成。麒麟 V10 真机的桌面行为、光驱权限、实际刻录和擦除回读仍需验证。
