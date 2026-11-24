# 观海·拾光 0.0.1 · 银河麒麟 V10 版

屏幕右侧的轻量光盘面板：只读设备检测、已挂载光盘浏览/导出、ISO 9660 + Joliet/Rock Ridge mastered 刻录、UDF 写入、快速/完整擦除、进度、取消、六套皮肤及随机启动动画。AMD64 与 ARM64 分别在对应架构的麒麟 V10 上构建。

## 运行环境

- 银河麒麟 V10 图形桌面，Python 3（构建时）及 Tk；程序运行不需要 Windows COM。
- `xorriso` 用于刻录、擦除、UDF 和弹出。正式单文件包优先使用内嵌工具；源码/开发运行也可查找程序旁 `tools/<amd64|arm64>/xorriso`，最后查找系统 PATH。
- 可选 `tkinterdnd2` 支持拖拽；缺失时仍可通过按钮添加文件，不影响其他功能。
- Linux 通常禁止普通用户直接写 `/dev/sr*`。请由管理员按单位安全策略配置 `cdrom` 组或 udev 权限；不要使用不受控的 sudo 提权。
- 读取前由麒麟桌面挂载光盘。写入/擦除前须在文件管理器中**卸载（不是弹出）**光盘。

## 一键离线构建

在**同架构、同麒麟 V10 版本**的构建机上：

```bash
cd kylin_desk
bash build_offline.sh
```

产物为 `dist/GuanHaiShiGuang`（PyInstaller onefile）。复制到目标机后直接执行，无需安装 Python，不访问网络：

```bash
chmod +x GuanHaiShiGuang
./GuanHaiShiGuang
```

若 `tools/<架构>/xorriso` 已提供且可执行，构建脚本会把它嵌入 `dist/GuanHaiShiGuang`，交付时只需这一个可执行文件，无需保留 `tools` 目录。未提供时脚本会明确警告，此时仍需从麒麟安装镜像离线安装 `xorriso`；不要把 AMD64 工具用于 ARM64。

### 准备离线 wheel

`offline_wheels/amd64` 和 `offline_wheels/arm64` 默认不在仓库中。联网准备机必须和目标构建机保持同架构、同 Python 主次版本；运行：

```bash
bash prepare_offline_deps.sh
```

随后将整个 `kylin_desk` 复制到隔离构建机。`build_offline.sh` 使用 `pip --no-index`，不会联网。若拖拽 wheel 不可得，从 `requirements-build.txt` 删除 `tkinterdnd2` 行后重跑，其他功能不受影响。

### 系统工具离线包

xorriso 属于系统原生工具，**不能通过 PyInstaller 从 Windows 交叉生成**。请从对应架构麒麟安装镜像的软件源取得 `xorriso` 及其动态库，或由系统包管理器离线安装。若自带可执行文件需连同其非系统动态库、许可证和运行路径一并验证；推荐优先使用系统包。

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
- 未提供托盘功能；关闭按钮最小化，记录页可退出。窗口管理器差异可能影响无边框面板置顶表现。
- 操作历史在 `$XDG_DATA_HOME/GuanHaiShiGuang/history.json`，皮肤在 `$XDG_CONFIG_HOME/GuanHaiShiGuang/settings.json`。

## 尚需真机验证

当前交付不包含 Linux 二进制。麒麟 AMD64/ARM64 的 PyInstaller 构建、Tk 字体/缩放、tkinterdnd2、udev 权限、各类型介质容量/空白状态、xorriso 版本兼容、刻录/擦除/UDF 挂载回读均须在目标真机与测试光盘上验证。部分内核/驱动对 CDROM capability 或 capacity ioctl 支持有限，应用会显示“未报告能力”或容量 0，而不会猜测成功。
