# Vita Gamepad

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-PS%20Vita%20%2B%20Windows-5C2D91)](#运行要求)
[![Build](https://github.com/zwt13703/vita-gamepad/actions/workflows/build.yml/badge.svg)](https://github.com/zwt13703/vita-gamepad/actions/workflows/build.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

把安装了 HENkaku 自制软件环境的 PlayStation Vita 变成低延迟无线游戏手柄。
Vita 通过局域网 Wi‑Fi 发送输入，Windows 端将其转换为标准 Xbox 360/XInput
虚拟手柄，并提供浏览器控制面板、按键映射和连击设置。

> 当前版本：电脑端 `0.4.1`，Vita 端 `01.06`。
>
> 当前仅启用 Wi‑Fi 连接；USB 功能仍处于停用状态。

项目地址：[github.com/zwt13703/vita-gamepad](https://github.com/zwt13703/vita-gamepad)

## 主要功能

- Wi‑Fi 双向发现，兼容 Windows 多网卡、VMware 和 VPN
- Vita 显示局域网内可连接电脑的数量和 IP，由用户手动选择
- 约 120 Hz 输入采样，输入变化立即发送
- 静止时自动降低网络和画面刷新频率，减少电量消耗
- Vita 右上角显示本地时间、电量、低电量提醒和充电状态
- 支持双摇杆、方向键、动作键、L1/R1、Start/Select
- 后触摸板左右半区模拟 L2/R2
- 前触摸板底部左右角模拟 L3/R3
- 断线 300 ms 后自动释放全部按键，避免卡键
- Windows 输出标准 Xbox 360/XInput 虚拟手柄
- 浏览器控制面板实时显示连接状态、按键、摇杆和日志
- 网页端自定义按键映射、禁用按键以及设置 1–30 Hz 连击

## 运行要求

### PSVita

- 安装了 HENkaku 的 PSVita
- VitaShell
- `vita-gamepad.vpk` `01.06` 或更高版本
- 与电脑处于同一局域网

### Windows

- Windows 10 或 Windows 11
- Python 3.10 或更高版本
- [ViGEmBus](https://github.com/nefarius/ViGEmBus/releases)

ViGEmBus 用于创建 Xbox 360 虚拟手柄。请安装官方签名版本，并在安装完成后
重启 Windows。

## Windows 快速开始

### 1. 获取项目

使用 HTTPS：

```powershell
git clone https://github.com/zwt13703/vita-gamepad.git
cd vita-gamepad
```

已经配置 GitHub SSH 密钥时也可以使用：

```powershell
git clone git@github.com:zwt13703/vita-gamepad.git
cd vita-gamepad
```

### 2. 安装电脑端

在项目目录打开 PowerShell：

```powershell
py -3 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[windows]"
```

以后再次运行只需激活现有虚拟环境：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. 安装 Vita 端

从项目的 [Releases](https://github.com/zwt13703/vita-gamepad/releases)
下载 `vita-gamepad.vpk`，传到 Vita 后通过 VitaShell 安装。相同 Title ID 的
旧版本可以直接覆盖。

如果 Releases 暂时没有 VPK，可以按照[构建 Vita VPK](#构建-vita-vpk)自行构建。

### 4. 启动电脑控制面板

```powershell
vitapad-gui
```

默认控制页面：

```text
http://127.0.0.1:8765/
```

如果端口被占用：

```powershell
vitapad-gui --ui-port 8876
```

Windows 首次弹出防火墙提示时，只允许“专用网络”。打开控制页面后点击
“开启使用”，程序才会创建虚拟手柄并开始广播电脑信息。

### 5. 在 Vita 上连接

1. 确认电脑和 Vita 连接同一个 Wi‑Fi/局域网。
2. 在电脑控制页面点击“开启使用”。
3. 打开 Vita Gamepad，等待扫描完成。
4. Vita 会显示 `Computers found` 和发现的电脑 IP。
5. 使用方向键上/下选择电脑，按 `×` 连接。
6. 连接成功后，Vita 会显示电脑 IP 和已发送数据包数量。
7. 在电脑控制页面检查实时按键和摇杆。
8. 按 `Win + R`，输入 `joy.cpl`，确认存在
   `Controller (XBOX 360 For Windows)`。

局域网内有多台运行中的电脑时，Vita 会按 IP 去重并显示最近仍在线的主机，
不会自动连接最先响应的电脑。当前最多显示 8 台，停止广播超过 5 秒的电脑会
从列表移除。

## 网页控制面板

控制面板提供：

- 开启或暂停虚拟手柄
- 查看 Vita IP、运行时间和当前后端
- 实时检查按键、摇杆和扳机输入
- 查看连接及错误日志
- 修改按键映射和连击设置

### 自定义按键和连击

Vita 的动作键、方向键、L1/R1、Start/Select、L2/R2 和 L3/R3 均可：

- 映射到任意 Xbox 数字按键、方向键或 LT/RT
- 选择“禁用”
- 独立开启或关闭连击
- 设置 1–30 Hz 连击频率

修改后点击“保存设置”，下一帧输入立即使用新配置。“恢复默认”只会恢复表格，
仍需点击“保存设置”才会生效。

Windows 默认配置文件：

```text
%APPDATA%\VitaGamepad\settings.json
```

指定其他配置文件：

```powershell
vitapad-gui --ui-port 8876 --config D:\gamepad\my-settings.json
```

连击频率表示每秒完整按下/松开循环次数。例如 `10 Hz` 约等于每秒 10 次按键。
摇杆 X/Y 轴保持模拟输入，不参与连击；L3/R3 可以映射和连击。

## 默认按键映射

| PS Vita | Xbox/XInput | PlayStation 名称 |
|---|---|---|
| × | A | Cross |
| ○ | B | Circle |
| □ | X | Square |
| △ | Y | Triangle |
| L / R | LB / RB | L1 / R1 |
| 后触摸板左 / 右 | LT / RT | L2 / R2 |
| Select / Start | Back / Start | Share / Options |
| 前触摸板左下 / 右下 | LS / RS | L3 / R3 |

## Vita 端操作

| 操作 | 按键 |
|---|---|
| 选择电脑 | 方向键上/下 |
| 连接选中的电脑 | `×` |
| 返回电脑选择列表 | `Start + ○` |
| 退出程序 | 按住 `Start + Select` 两秒 |

## 命令行

不打开浏览器控制面板：

```powershell
vitapad
```

只测试发现、网络和输入，不创建 Xbox 虚拟手柄：

```powershell
vitapad --backend debug
```

常用参数：

```text
--port 5000             输入端口
--discovery-port 5001   自动发现端口
--bind 0.0.0.0          监听地址
--allow 192.168.1.25    只接受指定 Vita IP
--timeout-ms 300        断线释放时间
--config PATH           按键配置文件路径
--ui-port 8765          网页端口（仅 vitapad-gui）
--no-browser            不自动打开浏览器（仅 vitapad-gui）
```

## 常见问题

### Vita 一直显示 0 台电脑

- 确认电脑控制页面已经点击“开启使用”。
- 确认 Windows 当前网络类型为“专用网络”。
- 允许 Python 或 `VitaGamepadDashboard.exe` 通过 Windows 防火墙。
- 检查路由器是否开启 AP/客户端隔离。
- 确认电脑和 Vita 没有分别连接访客网络与主网络。

### 无法创建虚拟手柄

确认设备管理器的“系统设备”中存在
`Nefarius Virtual Gamepad Emulation Bus`，然后重启电脑。

### 控制页面启动时报 `WinError 10013` 或 `10048`

网页端口通常已被其他程序占用，改用：

```powershell
vitapad-gui --ui-port 8876
```

如果 UDP `5000` 启动失败，请关闭其他 Vita Gamepad 实例或占用该端口的程序。

### PowerShell 禁止激活脚本

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

该命令只影响当前 PowerShell 窗口。

## 打包 Windows EXE

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

输出：

```text
dist\windows\VitaGamepadDashboard.exe
```

目标电脑仍需安装 ViGEmBus。

## GitHub Actions 自动构建

仓库内置的 [Build 工作流](.github/workflows/build.yml)会自动执行：

- 对 `main` 的 push 和 pull request 运行 Python 测试
- 构建 `VitaGamepadDashboard.exe`
- 使用 VitaSDK 构建 `vita-gamepad.vpk`
- 将 EXE 和 VPK 保存为 Actions Artifacts，保留 30 天
- 推送 `v*` 标签时创建 GitHub Release，并附带 SHA256 校验文件

### 手动构建

1. 打开 GitHub 仓库的 **Actions** 页面。
2. 选择左侧的 **Build**。
3. 点击 **Run workflow**。
4. 构建完成后，在运行详情页面底部下载 Artifacts。

### 发布版本

先更新 `pyproject.toml` 中的电脑端版本和 `vita/CMakeLists.txt` 中的 Vita 版本，
提交后创建版本标签。例如：

```powershell
git tag -a v0.4.1 -m "Vita Gamepad v0.4.1"
git push origin main
git push origin v0.4.1
```

标签推送完成后，GitHub Actions 会自动创建 Release，并上传：

```text
VitaGamepadDashboard.exe
vita-gamepad.vpk
SHA256SUMS.txt
```

## 构建 Vita VPK

需要 [VitaSDK](https://vitasdk.org/) 和 `libvita2d`：

```bash
cd vita
cmake -S . -B build
cmake --build build
```

输出：

```text
vita/build/vita-gamepad.vpk
```

仅在需要重新生成 LiveArea 图片时运行：

```bash
python3 assets/generate_assets.py
```

## macOS 与其他平台

macOS 可以运行 Wi‑Fi 接收、控制面板和 debug 后端。系统级虚拟 HID 后端仍属
实验性功能，可能受到 macOS entitlement 和签名策略限制。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
.venv/bin/vitapad --backend debug
```

Linux 目前适合使用 debug 后端验证网络和输入，不提供系统级虚拟手柄。

## 项目结构

```text
vitapad/                 电脑端 Python 程序
vitapad/backends/        Windows、macOS 和调试后端
vita/                    PSVita 应用源码与 LiveArea 资源
scripts/                 Windows 打包脚本
tests/                   自动化测试
docs/protocol.md         网络协议说明
```

## 协议与安全

协议说明见 [docs/protocol.md](docs/protocol.md)。输入包固定为 20 字节，不执行
远程命令，也不接收来自电脑的代码。协议没有鉴权或加密，只应在可信的家庭局域网
中使用。

## 开发测试

```bash
python -m unittest discover -s tests -v
```

提交问题或建议：
[GitHub Issues](https://github.com/zwt13703/vita-gamepad/issues)

## License

本项目使用 [MIT License](LICENSE)。
