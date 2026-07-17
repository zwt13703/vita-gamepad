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
- macOS 提供实验性通用 HID 后端；新版系统可能受 entitlement 限制

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

支持 Windows 10/11，电脑端会创建标准 Xbox 360/XInput 虚拟手柄。

#### 1. 安装虚拟手柄驱动

从 [ViGEmBus 官方 Releases](https://github.com/nefarius/ViGEmBus/releases)
下载并安装 `ViGEmBus Setup 1.22.0`。该项目已经归档，因此只建议从官方仓库
下载签名驱动，不要使用第三方重新打包版本。安装完成后建议重启一次 Windows。

#### 2. 安装 Vita Gamepad 电脑端

打开 PowerShell，进入本项目目录后运行：

```powershell
py -3 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[windows]"
vitapad-gui
```

程序会自动打开 `http://127.0.0.1:8765/` 控制面板。首次运行出现 Windows
防火墙提示时，只需允许“专用网络”访问，不建议开放公用网络。

#### 3. 连接与测试

1. 确保 Windows 电脑和 PSVita 连接同一个 Wi-Fi。
2. 在控制面板点击“开启使用”。
3. 打开 Vita Gamepad，等待页面显示 Vita IP。
4. 按 Vita 按键，页面中的对应按键会实时亮起；双摇杆和 L2/R2 也会跟随。
5. 按 `Win + R`，输入 `joy.cpl`，应能看到 `Controller (XBOX 360 For Windows)`。
6. 在该设备的“属性”页面可进一步检查 Windows 收到的按键和摇杆输入。

点击控制面板的“暂停”会立即释放按键、停止网络接收并移除虚拟手柄。

#### Windows 命令行模式

不需要控制面板时可运行：

```powershell
vitapad
```

只测试 Vita 网络和按键，不创建 Xbox 虚拟手柄：

```powershell
vitapad --backend debug
```

#### 打包 Windows EXE

已提供自动打包脚本。在 PowerShell 中运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

生成文件位于 `dist\windows\VitaGamepadDashboard.exe`。目标电脑仍需先安装
ViGEmBus 驱动。

#### Windows 常见问题

- 提示“无法创建虚拟手柄”：确认已安装 ViGEmBus，并在设备管理器的“系统设备”
  中检查 `Nefarius Virtual Gamepad Emulation Bus`，然后重启电脑。
- 控制页面没有自动打开：手动访问 `http://127.0.0.1:8765/`。
- 一直等待 Vita：确认网络类型为“专用网络”，允许 Python 或
  `VitaGamepadDashboard.exe` 通过防火墙，并检查路由器没有开启 AP/客户端隔离。
- PowerShell 禁止运行激活脚本：重新执行
  `Set-ExecutionPolicy -Scope Process Bypass`，它只影响当前窗口。
- `5000` 端口被占用：关闭其他 Vita Gamepad 实例或占用该端口的程序；当前
  Vita 端固定使用 UDP 5000。

### macOS

> [!WARNING]
> macOS 没有正式、稳定的系统级虚拟游戏手柄 API。当前实验性
> `IOHIDUserDevice` 后端在旧版系统上可尝试通过管理员权限运行，但在
> macOS 26 等新版系统上可能仍被 entitlement/签名策略拒绝。控制面板和实时
> 按键测试可以使用 `--backend debug`，但该模式不会向游戏创建虚拟手柄。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
sudo .venv/bin/vitapad
```

macOS 后端通过 `IOHIDUserDevice` 尝试创建通用 HID 手柄，需要管理员权限，
且不保证能被当前系统或游戏接受。

使用预编译的 Apple Silicon 接收端时，解压后运行：

```bash
sudo ./VitaGamepadReceiver
```

如果 macOS 阻止首次打开，可在“系统设置 → 隐私与安全性”中允许，或执行：

```bash
xattr -dr com.apple.quarantine VitaGamepadReceiver
```

### 图形控制面板

预编译的 `VitaGamepadDashboard` 启动后会自动打开本机控制页面，页面只监听
`127.0.0.1`。可以在其中：

- 点击“开启使用”创建虚拟手柄并开始自动发现 Vita
- 点击“暂停”立即释放全部按键并停止接收
- 查看运行状态、Vita IP、运行时间和端口
- 在手柄预览中实时检查按键高亮、双摇杆位置和 L2/R2 压力
- 查看连接、断线、重连和错误日志

macOS 需要通过终端以管理员权限启动：

```bash
sudo ./VitaGamepadDashboard
```

关闭浏览器页面不会结束接收程序；需要结束程序时在终端按 `Control-C`。

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
python3 assets/generate_assets.py  # 仅在需要重新生成 LiveArea 图片时运行
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
