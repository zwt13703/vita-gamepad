# Vita Gamepad

把一台已安装 HENkaku/enso 的 PlayStation Vita 通过局域网变成 Windows 或
macOS 游戏手柄。

## 功能

- 同一 Wi-Fi 下自动发现电脑，无需在 Vita 上输入 IP
- 约 120 Hz 的 UDP 输入传输
- 双摇杆、方向键、四个动作键、L1/R1、Start/Select
- 后触摸板左右半区模拟 L2/R2
- 前触摸板底部左右角模拟 L3/R3
- 断线 300 ms 后自动释放全部按键，避免卡键
- Windows 输出标准 Xbox 360/XInput 虚拟手柄
- macOS 输出通用 HID 游戏手柄

## 按键映射

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

## 电脑端

需要 Python 3.10 或更高版本。建议先创建虚拟环境。

### Windows

1. 安装 [ViGEmBus](https://github.com/nefarius/ViGEmBus/releases)。
2. 在 PowerShell 中运行：

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[windows]"
vitapad
```

首次运行时允许 Windows 防火墙的“专用网络”访问。程序创建的是 Xbox 360
控制器，Steam、Xbox 应用和绝大多数 Windows 游戏都能直接识别。

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
sudo .venv/bin/vitapad
```

macOS 后端通过 `IOHIDUserDevice` 创建通用 HID 手柄，通常需要管理员权限。
Apple 并未把用户态虚拟游戏手柄作为稳定的 Game Controller API 保证；个别只
接受 Apple Game Controller Framework 设备的游戏可能不会显示它。Steam 游戏可
在“控制器”设置中启用 Steam Input 以提高兼容性。

### 仅测试网络，不创建手柄

```bash
vitapad --backend debug
```

收到数据后会在终端显示按键和摇杆状态，适合排查防火墙或 Wi-Fi 隔离问题。

可选参数：

```text
--port 5000             输入端口
--discovery-port 5001   自动发现端口
--bind 0.0.0.0          监听地址
--allow 192.168.1.25    只接受指定 Vita IP
--timeout-ms 300        断线释放时间
```

## PSVita 端构建与安装

需要安装 [VitaSDK](https://vitasdk.org/) 和 `vita2dlib`：

```bash
cd vita
cmake -S . -B build
cmake --build build
```

将 `build/vita-gamepad.vpk` 传到 Vita 并用 VitaShell 安装。启动电脑端
`vitapad` 后再打开 Vita Gamepad；两台设备必须在同一局域网，且路由器不能启用
客户端/AP 隔离。

Vita 界面显示电脑 IP 和已发送包数。按住 `Start + Select` 两秒可退出。

## 网络协议

协议说明见 [docs/protocol.md](docs/protocol.md)。它只有固定 20 字节，不执行
远程命令，也不接收来自电脑的代码。自动发现只发送一个固定文本信标。

## 开发测试

```bash
python -m unittest discover -s tests -v
```

