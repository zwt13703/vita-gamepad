# Vita Gamepad

把安装了 HENkaku 自制软件环境的 PlayStation Vita 变成 Windows 或 macOS
游戏手柄。Vita 可以通过同一局域网的 Wi‑Fi 或 USB 数据线发送输入。

## 功能

- Wi‑Fi 双向发现，兼容 Windows 多网卡、VMware 和 VPN
- Vita 显示局域网内可连接电脑的数量与 IP，由用户选择目标
- Wi‑Fi 与 USB 数据线模式可随时切换
- 约 120 Hz 的低延迟输入传输
- 双摇杆、方向键、动作键、L1/R1、Start/Select
- 后触摸板左右半区模拟 L2/R2
- 前触摸板底部左右角模拟 L3/R3
- 断线 300 ms 后自动释放全部按键，避免卡键
- Windows 输出标准 Xbox 360/XInput 虚拟手柄
- 浏览器控制面板实时显示按键、摇杆、连接状态和日志

## Windows 使用步骤

### 1. 准备环境

需要：

- Windows 10 或 Windows 11
- Python 3.10 或更高版本
- 已安装新版 VPK 的 PSVita
- Wi‑Fi 模式下，电脑和 Vita 必须连接同一局域网

电脑端通过 ViGEmBus 创建 Xbox 360 虚拟手柄。从
[ViGEmBus 官方 Releases](https://github.com/nefarius/ViGEmBus/releases)
下载并安装官方签名版本，完成后重启 Windows。

### 2. 安装电脑端

在项目目录打开 PowerShell：

```powershell
py -3 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[windows,usb]"
```

以后再次使用时，只需进入项目目录并激活现有虚拟环境：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
```

### 3. 启动控制面板

```powershell
vitapad-gui
```

程序会打开：

```text
http://127.0.0.1:8765/
```

如果 `8765` 已被其他程序占用，可以指定别的网页端口：

```powershell
vitapad-gui --ui-port 8876
```

Windows 首次弹出防火墙提示时，只允许“专用网络”。进入控制面板后点击
“开启使用”，程序才会创建虚拟手柄并开始等待 Vita。

### 4. 安装 Vita 端

把新版 `vita-gamepad.vpk` 传到 Vita，并通过 VitaShell 安装。相同 Title ID
的旧版本可以直接覆盖。

如果自行构建，生成文件位于：

```text
vita/build/vita-gamepad.vpk
```

### 5. 使用 Wi‑Fi 连接

1. 确认电脑和 Vita 连接同一个 Wi‑Fi/局域网。
2. 在电脑控制面板点击“开启使用”。
3. 打开 Vita Gamepad，等待扫描完成。
4. Vita 会显示 `Computers found` 和发现的电脑 IP。
5. 使用方向键上/下选择电脑，按 `×` 建立连接。
6. 连接成功后，Vita 显示电脑 IP 和已发送数据包数量。
7. 在电脑控制面板检查实时按键和摇杆。
8. 按 `Win + R`，输入 `joy.cpl`，应看到
   `Controller (XBOX 360 For Windows)`。

同一局域网有多台运行中的电脑时，Vita 按 IP 去重并显示最近仍在线的主机，
不会再自动连接最先响应的电脑。当前最多显示 8 台；停止广播超过 5 秒的电脑会
从列表移除。

连接后按 `Start + ○` 可以断开当前电脑并返回主机选择列表。

### 6. 使用 USB 数据线连接

USB 模式目前主要面向 Windows，使用 VitaSDK 的 USB Serial 数据通道。

1. 电脑控制面板保持“开启使用”。
2. 在 Vita 中按 `Start + △`，切换到 `USB cable`。
3. 使用支持数据传输的 USB 线连接 Vita 和电脑。
4. Windows 设备管理器应出现 `PS Vita Type D`。
5. 首次使用时，通过 [Zadig](https://zadig.akeo.ie/) 只为
   `PS Vita Type D` 安装 `WinUSB`。
6. 检测成功后，Vita 显示 `Connected: USB`。

再次按 `Start + △` 可以切回 Wi‑Fi。安装 WinUSB 时不要替换普通内容管理或
VitaShell 使用的 Type B 设备驱动。

## Vita 端操作

| 操作 | 按键 |
|---|---|
| 选择电脑 | 方向键上/下 |
| 连接选中的电脑 | `×` |
| 返回电脑选择列表 | `Start + ○` |
| 切换 Wi‑Fi / USB | `Start + △` |
| 退出程序 | 按住 `Start + Select` 两秒 |

## 游戏按键映射

| PS Vita | Xbox 游戏内名称 | PlayStation 名称 |
|---|---|---|
| × | A | Cross |
| ○ | B | Circle |
| □ | X | Square |
| △ | Y | Triangle |
| L / R | LB / RB | L1 / R1 |
| 后触摸板左 / 右 | LT / RT | L2 / R2 |
| Select / Start | Back / Start | Share / Options |
| 前触摸板左下 / 右下 | LS / RS | L3 / R3 |

## 命令行和调试

不使用浏览器控制面板：

```powershell
vitapad
```

只测试发现、网络和按键，不创建 Xbox 虚拟手柄：

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
--ui-port 8765          控制面板网页端口（仅 vitapad-gui）
--no-browser            不自动打开浏览器（仅 vitapad-gui）
```

## Windows 常见问题

- Vita 找不到电脑：先确认控制面板已经点击“开启使用”，网络类型为“专用网络”，
  并允许 Python 或 `VitaGamepadDashboard.exe` 通过防火墙。
- 仍然显示 0 台电脑：检查路由器是否开启 AP/客户端隔离，并确认电脑与 Vita
  不是分别连接访客网络和主网络。
- 无法创建虚拟手柄：确认设备管理器的“系统设备”中存在
  `Nefarius Virtual Gamepad Emulation Bus`，然后重启电脑。
- 控制页面启动失败：`WinError 10013` 或 `10048` 通常表示网页端口已被占用，
  使用 `vitapad-gui --ui-port 8876`。
- 输入端口启动失败：关闭占用 UDP `5000` 的程序或其他 Vita Gamepad 实例。
- USB 找不到设备：确认使用数据线而非仅充电线，并检查 Type D 设备使用的是
  WinUSB 驱动。
- PowerShell 禁止激活脚本：执行
  `Set-ExecutionPolicy -Scope Process Bypass`，它只影响当前窗口。

## 打包 Windows EXE

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

输出文件：

```text
dist\windows\VitaGamepadDashboard.exe
```

目标电脑仍需安装 ViGEmBus。USB 模式首次使用仍需配置 Type D 的 WinUSB。

## macOS

macOS 可以运行控制面板、Wi‑Fi 接收和 debug 后端，但系统级虚拟 HID 后端是
实验性的，新版 macOS 可能因为 entitlement/签名策略拒绝创建虚拟手柄。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
sudo .venv/bin/vitapad
```

仅验证 Vita 连接和输入时建议：

```bash
.venv/bin/vitapad --backend debug
```

## 构建 Vita VPK

需要 [VitaSDK](https://vitasdk.org/) 和 `libvita2d`：

```bash
cd vita
cmake -S . -B build
cmake --build build
```

仅在需要重新生成 LiveArea 图片时运行：

```bash
python3 assets/generate_assets.py
```

VPK 输出路径：

```text
vita/build/vita-gamepad.vpk
```

## 协议与安全

协议说明见 [docs/protocol.md](docs/protocol.md)。输入包固定为 20 字节，不执行
远程命令，也不接收来自电脑的代码。协议没有鉴权或加密，只应在可信的家庭局域网
中使用。

## 开发测试

```bash
python -m unittest discover -s tests -v
```
