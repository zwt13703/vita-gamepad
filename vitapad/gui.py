from __future__ import annotations

import argparse
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import queue
import secrets
import threading
import time
from urllib.parse import parse_qs, urlparse
import webbrowser

from vitapad.backends import create_backend
from vitapad.mapping import MappingManager
from vitapad.protocol import InputState
from vitapad.receiver import Receiver


@dataclass(frozen=True, slots=True)
class LogEntry:
    id: int
    time: str
    level: str
    message: str


class DashboardController:
    def __init__(
        self,
        backend_name: str,
        bind: str,
        port: int,
        discovery_port: int,
        allow: str | None,
        timeout_ms: int,
        config_path: str | None = None,
    ) -> None:
        self.backend_name = backend_name
        self._resolved_backend = backend_name
        self.bind = bind
        self.port = port
        self.discovery_port = discovery_port
        self.allow = allow
        self.timeout_ms = timeout_ms
        self.mapping = MappingManager(config_path)
        self._lock = threading.RLock()
        self._status = "paused"
        self._receiver: Receiver | None = None
        self._worker: threading.Thread | None = None
        self._started_at: float | None = None
        self._error: str | None = None
        self._stop_requested = False
        self._logs: deque[LogEntry] = deque(maxlen=500)
        self._next_log_id = 1
        self._input = InputState.neutral()
        self._subscribers: set[queue.Queue[InputState]] = set()
        self.log("控制面板已启动，点击“开启使用”开始接收。")

    def log(self, message: str, level: str = "info") -> None:
        with self._lock:
            entry = LogEntry(
                id=self._next_log_id,
                time=datetime.now().strftime("%H:%M:%S"),
                level=level,
                message=message,
            )
            self._next_log_id += 1
            self._logs.append(entry)

    def start(self) -> tuple[bool, str]:
        with self._lock:
            if self._status in {"starting", "running"}:
                return False, "接收服务已经开启"
            if self._status == "stopping":
                return False, "服务正在暂停，请稍候"
            self._status = "starting"
            self._error = None
            self._stop_requested = False
            self.log("正在创建虚拟手柄并启动网络服务...")
            self._worker = threading.Thread(
                target=self._run_receiver, name="receiver", daemon=True
            )
            self._worker.start()
            return True, "正在开启"

    def _run_receiver(self) -> None:
        try:
            backend = create_backend(self.backend_name)
            receiver = Receiver(
                backend=backend,
                bind=self.bind,
                port=self.port,
                discovery_port=self.discovery_port,
                allow=self.allow,
                timeout_ms=self.timeout_ms,
                log=self.log,
                on_input=self.handle_input,
                mapping=self.mapping,
            )
            with self._lock:
                if self._stop_requested:
                    backend.close()
                    self.log("服务已暂停。")
                    return
                self._resolved_backend = backend.name
                self._receiver = receiver
                self._status = "running"
                self._started_at = time.monotonic()
                self.log(f"服务已开启，虚拟手柄后端：{backend.name}", "success")
            receiver.run()
        except Exception as exc:
            with self._lock:
                self._error = str(exc)
                self.log(f"启动失败：{exc}", "error")
        finally:
            with self._lock:
                if self._stop_requested:
                    self.log("服务已暂停，虚拟手柄已释放。", "success")
                self._receiver = None
                self._started_at = None
                self._status = "paused"

    def pause(self) -> tuple[bool, str]:
        with self._lock:
            if self._status == "paused":
                return False, "接收服务已经暂停"
            if self._status == "stopping":
                return False, "服务正在暂停"
            self._status = "stopping"
            self._stop_requested = True
            receiver = self._receiver
            self.log("正在暂停，释放全部手柄按键...")
            if receiver is not None:
                receiver.stop()
            return True, "正在暂停"

    def status(self) -> dict[str, object]:
        with self._lock:
            connected = (
                self._receiver.connected_address if self._receiver else None
            )
            uptime = (
                int(time.monotonic() - self._started_at)
                if self._started_at is not None
                else 0
            )
            return {
                "status": self._status,
                "connected": connected,
                "uptime": uptime,
                "backend": self._resolved_backend,
                "inputPort": self.port,
                "discoveryPort": self.discovery_port,
                "error": self._error,
                "input": asdict(self._input),
            }

    def logs_after(self, after: int) -> list[dict[str, object]]:
        with self._lock:
            return [asdict(entry) for entry in self._logs if entry.id > after]

    def settings(self) -> dict[str, object]:
        return self.mapping.describe()

    def update_settings(self, payload: dict[str, object]) -> None:
        self.mapping.update(payload)
        self.log("按键映射和连击设置已保存。", "success")

    def handle_input(self, state: InputState) -> None:
        with self._lock:
            self._input = state
            subscribers = tuple(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber.put_nowait(state)
            except queue.Full:
                try:
                    subscriber.get_nowait()
                    subscriber.put_nowait(state)
                except (queue.Empty, queue.Full):
                    pass

    def subscribe(self) -> queue.Queue[InputState]:
        subscriber: queue.Queue[InputState] = queue.Queue(maxsize=16)
        with self._lock:
            self._subscribers.add(subscriber)
            subscriber.put_nowait(self._input)
        return subscriber

    def unsubscribe(self, subscriber: queue.Queue[InputState]) -> None:
        with self._lock:
            self._subscribers.discard(subscriber)


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vita Gamepad</title>
<style>
:root{color-scheme:dark;--bg:#0e1420;--panel:#171f2f;--line:#29364b;--text:#f4f7fb;--muted:#9cabc1;--green:#26be7d;--green2:#50e19b;--red:#ff6b78;--amber:#f4c653}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 85% 10%,#17392f 0,transparent 30%),var(--bg);color:var(--text);font:15px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;min-height:100vh}
.wrap{width:min(920px,calc(100% - 32px));margin:40px auto}.top{display:flex;align-items:center;gap:15px;margin-bottom:24px}.logo{width:54px;height:54px;border:2px solid var(--green);border-radius:16px;display:grid;place-items:center;color:var(--green2);font-size:25px}.top h1{font-size:25px;margin:0}.top p{color:var(--muted);margin:4px 0 0}
.grid{display:grid;grid-template-columns:1.1fr .9fr;gap:18px}.card{background:rgba(23,31,47,.94);border:1px solid var(--line);border-radius:18px;padding:22px;box-shadow:0 18px 60px #0004}.statusline{display:flex;align-items:center;gap:10px}.dot{width:11px;height:11px;border-radius:50%;background:#66758b;box-shadow:0 0 0 5px #66758b22}.dot.running{background:var(--green2);box-shadow:0 0 0 5px #50e19b22}.dot.starting,.dot.stopping{background:var(--amber);box-shadow:0 0 0 5px #f4c65322}.state{font-size:20px;font-weight:650}.meta{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:24px 0}.item{background:#101725;border:1px solid #243047;border-radius:12px;padding:13px}.label{color:var(--muted);font-size:12px;margin-bottom:6px}.value{font-variant-numeric:tabular-nums;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.actions{display:flex;gap:11px}.btn{border:0;border-radius:11px;padding:12px 19px;font-weight:650;font-size:14px;cursor:pointer;transition:.15s}.btn:hover{transform:translateY(-1px)}.btn:disabled{opacity:.42;cursor:not-allowed;transform:none}.start{background:var(--green);color:#07140e}.pause{background:#303c50;color:var(--text)}
.logcard{grid-column:1/-1;padding:0;overflow:hidden}.loghead{display:flex;justify-content:space-between;align-items:center;padding:17px 20px;border-bottom:1px solid var(--line)}.loghead h2{font-size:15px;margin:0}.clear{color:var(--muted);background:none;border:0;cursor:pointer}.logs{height:310px;overflow:auto;padding:10px 0;font:13px ui-monospace,SFMono-Regular,Menlo,monospace}.entry{display:grid;grid-template-columns:72px 72px 1fr;gap:8px;padding:7px 20px}.entry:hover{background:#ffffff06}.time{color:#718198}.level{color:#91a2ba}.level.success{color:var(--green2)}.level.error{color:var(--red)}.message{white-space:pre-wrap;word-break:break-word}.hint{color:var(--muted);font-size:13px;line-height:1.65;margin:0}.errorbox{display:none;background:#3b1d27;border:1px solid #7b3345;color:#ffadb7;padding:11px 13px;border-radius:10px;margin-top:15px}
.testcard{grid-column:1/-1;padding:18px 22px}.testhead{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:5px}.testhead h2{font-size:15px;margin:0}.pressed{color:var(--muted);font:12px ui-monospace,SFMono-Regular,Menlo,monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gamepad{display:block;width:100%;max-height:360px;transition:opacity .2s}.gamepad.disconnected{opacity:.45}.shell{fill:#101725;stroke:#34435b;stroke-width:5}.pad-btn{fill:#263349;stroke:#617089;stroke-width:3;transition:fill .06s,stroke .06s,filter .06s}.pad-btn.active{fill:var(--green);stroke:var(--green2);filter:drop-shadow(0 0 8px #50e19baa)}.pad-label{fill:#dce4ef;font:500 15px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;text-anchor:middle;dominant-baseline:central;pointer-events:none}.stick-ring{fill:#1a2435;stroke:#53627a;stroke-width:5}.stick.active .stick-ring{stroke:var(--green2);filter:drop-shadow(0 0 8px #50e19b88)}.stick-knob{fill:#334158;stroke:#718099;stroke-width:3;transition:transform .025s linear}.trigger-track{fill:#263349}.trigger-fill{fill:var(--green2);transition:height .025s linear,y .025s linear}.trigger-label{fill:#9cabc1;font:500 13px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;text-anchor:middle}.center-label{fill:#728198;font:500 11px ui-monospace,SFMono-Regular,Menlo,monospace;text-anchor:middle}
.settingscard{grid-column:1/-1}.settingshead{display:flex;justify-content:space-between;align-items:flex-start;gap:20px;margin-bottom:16px}.settingshead h2{font-size:16px;margin:0 0 5px}.settingshead p{color:var(--muted);font-size:12px;margin:0}.settingrows{display:grid;gap:7px}.settingrow{display:grid;grid-template-columns:1.1fr 1.4fr .65fr .65fr;gap:10px;align-items:center;background:#101725;border:1px solid #243047;border-radius:10px;padding:9px 12px}.settingrow.head{background:none;border:0;color:var(--muted);font-size:12px;padding-block:0}.settingrow select,.settingrow input[type=number]{width:100%;background:#182235;color:var(--text);border:1px solid #34435b;border-radius:8px;padding:8px}.turboctl{display:flex;align-items:center;gap:7px}.settingsactions{display:flex;align-items:center;gap:10px;margin-top:15px}.savehint{color:var(--muted);font-size:12px}
@media(max-width:680px){.grid{grid-template-columns:1fr}.wrap{margin:22px auto}.meta{grid-template-columns:1fr}.entry{grid-template-columns:62px 58px 1fr;padding-inline:13px}.settingrow{grid-template-columns:1fr 1fr}.settingrow.head{display:none}}
</style>
</head>
<body><main class="wrap">
<div class="top"><div class="logo">⌁</div><div><h1>Vita Gamepad</h1><p>局域网虚拟游戏手柄控制台</p></div></div>
<section class="grid">
<div class="card">
  <div class="statusline"><span id="dot" class="dot"></span><span id="state" class="state">已暂停</span></div>
  <div class="meta">
    <div class="item"><div class="label">PSVita 连接</div><div id="vita" class="value">尚未连接</div></div>
    <div class="item"><div class="label">运行时间</div><div id="uptime" class="value">00:00:00</div></div>
    <div class="item"><div class="label">输入端口</div><div id="port" class="value">5000</div></div>
    <div class="item"><div class="label">虚拟手柄</div><div id="backend" class="value">自动选择</div></div>
  </div>
  <div class="actions"><button id="start" class="btn start">开启使用</button><button id="pause" class="btn pause">暂停</button></div>
  <div id="error" class="errorbox"></div>
</div>
<div class="card"><p class="hint">开启后，程序会等待同一局域网内的 PSVita Wi-Fi 连接。双向发现兼容多网卡、VMware 和 VPN 环境。<br><br>在 Vita 端从列表中选择电脑 IP，按 × 连接；连接后按 START + ○ 可以重新选择电脑。<br><br>暂停时会释放全部按键并移除虚拟手柄；关闭网页不会停止后台接收服务。</p></div>
<div class="card testcard">
  <div class="testhead"><h2>实时按键测试</h2><div id="pressed" class="pressed">等待手柄输入</div></div>
  <svg id="gamepad" class="gamepad disconnected" viewBox="0 0 760 330" role="img" aria-label="PSVita 实时手柄输入预览">
    <path class="shell" d="M176 60C113 64 79 100 59 172L27 270c-13 41 25 66 61 39l82-60h420l82 60c36 27 74 2 61-39l-32-98c-20-72-54-108-117-112z"/>
    <rect class="pad-btn" data-mask="16" x="126" y="68" width="116" height="31" rx="12"/><text class="pad-label" x="184" y="84">L1</text>
    <rect class="pad-btn" data-mask="32" x="518" y="68" width="116" height="31" rx="12"/><text class="pad-label" x="576" y="84">R1</text>
    <g><rect class="trigger-track" x="88" y="52" width="22" height="76" rx="8"/><rect id="ltFill" class="trigger-fill" x="88" y="128" width="22" height="0" rx="8"/><text class="trigger-label" x="99" y="42">L2</text></g>
    <g><rect class="trigger-track" x="650" y="52" width="22" height="76" rx="8"/><rect id="rtFill" class="trigger-fill" x="650" y="128" width="22" height="0" rx="8"/><text class="trigger-label" x="661" y="42">R2</text></g>
    <g aria-label="方向键">
      <rect class="pad-btn" data-mask="1024" x="142" y="113" width="46" height="53" rx="8"/><text class="pad-label" x="165" y="139">▲</text>
      <rect class="pad-btn" data-mask="2048" x="142" y="199" width="46" height="53" rx="8"/><text class="pad-label" x="165" y="226">▼</text>
      <rect class="pad-btn" data-mask="4096" x="99" y="156" width="53" height="46" rx="8"/><text class="pad-label" x="125" y="179">◀</text>
      <rect class="pad-btn" data-mask="8192" x="178" y="156" width="53" height="46" rx="8"/><text class="pad-label" x="205" y="179">▶</text>
      <rect x="151" y="165" width="28" height="29" rx="5" fill="#263349"/>
    </g>
    <g aria-label="动作键">
      <circle class="pad-btn" data-mask="8" cx="595" cy="128" r="24"/><text class="pad-label" x="595" y="128">△</text>
      <circle class="pad-btn" data-mask="2" cx="643" cy="176" r="24"/><text class="pad-label" x="643" y="176">○</text>
      <circle class="pad-btn" data-mask="1" cx="595" cy="224" r="24"/><text class="pad-label" x="595" y="224">×</text>
      <circle class="pad-btn" data-mask="4" cx="547" cy="176" r="24"/><text class="pad-label" x="547" y="176">□</text>
    </g>
    <rect class="pad-btn" data-mask="64" x="306" y="135" width="55" height="26" rx="13"/><text class="center-label" x="333" y="179">SELECT</text>
    <rect class="pad-btn" data-mask="128" x="399" y="135" width="55" height="26" rx="13"/><text class="center-label" x="426" y="179">START</text>
    <g id="leftStick" class="stick" data-mask="256"><circle class="stick-ring" cx="285" cy="232" r="42"/><circle id="leftKnob" class="stick-knob" cx="285" cy="232" r="23"/><text class="center-label" x="285" y="292">L3</text></g>
    <g id="rightStick" class="stick" data-mask="512"><circle class="stick-ring" cx="475" cy="232" r="42"/><circle id="rightKnob" class="stick-knob" cx="475" cy="232" r="23"/><text class="center-label" x="475" y="292">R3</text></g>
    <circle cx="380" cy="216" r="27" fill="#1a2435" stroke="#34435b" stroke-width="4"/><path d="M367 216h26M380 203v26" stroke="#718099" stroke-width="3" stroke-linecap="round"/>
  </svg>
</div>
<div class="card settingscard">
  <div class="settingshead"><div><h2>按键映射与连击</h2><p>修改后立即生效并保存到本机；频率范围 1–30 Hz。</p></div></div>
  <div class="settingrow head"><span>Vita 输入</span><span>Xbox 输出</span><span>连击</span><span>频率</span></div>
  <div id="settingRows" class="settingrows"></div>
  <div class="settingsactions"><button id="saveSettings" class="btn start">保存设置</button><button id="resetSettings" class="btn pause">恢复默认</button><span id="settingsMessage" class="savehint"></span></div>
</div>
<div class="card logcard"><div class="loghead"><h2>运行日志</h2><button id="clear" class="clear">清空显示</button></div><div id="logs" class="logs"></div></div>
</section></main>
<script>
const TOKEN="__TOKEN__";let last=0;const $=id=>document.getElementById(id);
const labels={paused:"已暂停",starting:"正在开启",running:"运行中",stopping:"正在暂停"};
const buttonNames=[[1,"×"],[2,"○"],[4,"□"],[8,"△"],[16,"L1"],[32,"R1"],[64,"Select"],[128,"Start"],[256,"L3"],[512,"R3"],[1024,"上"],[2048,"下"],[4096,"左"],[8192,"右"]];
function duration(n){const h=String(Math.floor(n/3600)).padStart(2,"0"),m=String(Math.floor(n%3600/60)).padStart(2,"0"),s=String(n%60).padStart(2,"0");return `${h}:${m}:${s}`}
async function api(path,method="GET",body=null){const headers={"X-Vita-Token":TOKEN};if(body!==null)headers["Content-Type"]="application/json";const r=await fetch(path,{method,headers,body:body===null?null:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw new Error(data.error||`HTTP ${r.status}`);return data}
function updateInput(i){if(!i)return;document.querySelectorAll("[data-mask]").forEach(el=>el.classList.toggle("active",Boolean(i.buttons&Number(el.dataset.mask))));const move=(id,x,y)=>$(id).setAttribute("transform",`translate(${((x-128)/127*18).toFixed(1)} ${((y-128)/127*18).toFixed(1)})`);move("leftKnob",i.lx,i.ly);move("rightKnob",i.rx,i.ry);const trigger=(id,v)=>{const h=v/255*76;$(id).setAttribute("y",128-h);$(id).setAttribute("height",h)};trigger("ltFill",i.lt);trigger("rtFill",i.rt);const names=buttonNames.filter(([m])=>i.buttons&m).map(([,n])=>n);if(i.lt)names.push(`L2 ${Math.round(i.lt/255*100)}%`);if(i.rt)names.push(`R2 ${Math.round(i.rt/255*100)}%`);$("pressed").textContent=names.length?names.join("  ·  "):"无按键按下"}
async function refresh(){try{const s=await api("/api/status");$("state").textContent=labels[s.status]||s.status;$("dot").className="dot "+s.status;$("vita").textContent=s.connected||"尚未连接";$("gamepad").classList.toggle("disconnected",!s.connected);$("uptime").textContent=duration(s.uptime);$("port").textContent=`${s.inputPort} / 发现 ${s.discoveryPort}`;$("backend").textContent=s.backend;$("start").disabled=["running","starting","stopping"].includes(s.status);$("pause").disabled=["paused","stopping"].includes(s.status);$("error").style.display=s.error?"block":"none";$("error").textContent=s.error||"";updateInput(s.input);const logs=await api("/api/logs?after="+last);for(const e of logs.logs){last=Math.max(last,e.id);const row=document.createElement("div");row.className="entry";row.innerHTML=`<span class="time">${e.time}</span><span class="level ${e.level}">${e.level}</span><span class="message"></span>`;row.lastChild.textContent=e.message;$("logs").appendChild(row);$("logs").scrollTop=$("logs").scrollHeight}}catch(e){}}
$("start").onclick=()=>api("/api/start","POST").then(refresh);$("pause").onclick=()=>api("/api/pause","POST").then(refresh);$("clear").onclick=()=>{$("logs").replaceChildren()};refresh();setInterval(refresh,750);
let settingsData=null;
function renderSettings(data,useDefaults=false){settingsData=data;const bindings=useDefaults?data.defaults:data.bindings;$("settingRows").replaceChildren();for(const source of data.sources){const value=bindings[source.id],row=document.createElement("div");row.className="settingrow";const label=document.createElement("span");label.textContent=source.label;const select=document.createElement("select");select.dataset.source=source.id;for(const target of data.targets){const option=document.createElement("option");option.value=target.id;option.textContent=target.label;option.selected=target.id===value.target;select.appendChild(option)}const turboWrap=document.createElement("label");turboWrap.className="turboctl";const turbo=document.createElement("input");turbo.type="checkbox";turbo.checked=value.turbo;turbo.dataset.turbo=source.id;turboWrap.append(turbo,document.createTextNode("开启"));const hz=document.createElement("input");hz.type="number";hz.min="1";hz.max="30";hz.step="1";hz.value=value.frequency;hz.dataset.frequency=source.id;row.append(label,select,turboWrap,hz);$("settingRows").appendChild(row)}}
function collectSettings(){const bindings={};for(const source of settingsData.sources){bindings[source.id]={target:document.querySelector(`[data-source="${source.id}"]`).value,turbo:document.querySelector(`[data-turbo="${source.id}"]`).checked,frequency:Number(document.querySelector(`[data-frequency="${source.id}"]`).value)}}return {version:1,bindings}}
async function loadSettings(){try{renderSettings(await api("/api/settings"))}catch(e){$("settingsMessage").textContent=e.message}}
$("saveSettings").onclick=async()=>{try{await api("/api/settings","POST",collectSettings());$("settingsMessage").textContent="已保存并立即生效";setTimeout(()=>$("settingsMessage").textContent="",2500)}catch(e){$("settingsMessage").textContent=e.message}};
$("resetSettings").onclick=()=>{if(settingsData){renderSettings(settingsData,true);$("settingsMessage").textContent="默认值已载入，点击保存后生效"}};
loadSettings();
const events=new EventSource("/api/events?token="+encodeURIComponent(TOKEN));events.onmessage=e=>{try{updateInput(JSON.parse(e.data))}catch(_){}};
</script></body></html>"""


def make_handler(
    controller: DashboardController, token: str
) -> type[BaseHTTPRequestHandler]:
    page = HTML.replace("__TOKEN__", token).encode()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: object) -> None:
            return

        def _authorized(self) -> bool:
            return self.headers.get("X-Vita-Token") == token

        def _json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _read_json(self) -> dict[str, object]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise ValueError("Content-Length 无效") from exc
            if not 0 < length <= 65536:
                raise ValueError("请求内容为空或过大")
            try:
                payload = json.loads(self.rfile.read(length))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("JSON 格式无效") from exc
            if not isinstance(payload, dict):
                raise ValueError("JSON 根节点必须是对象")
            return payload

        def _events(self) -> None:
            subscriber = controller.subscribe()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            try:
                while True:
                    try:
                        state = subscriber.get(timeout=10)
                        payload = json.dumps(
                            asdict(state), ensure_ascii=False, separators=(",", ":")
                        )
                        self.wfile.write(f"data:{payload}\n\n".encode())
                    except queue.Empty:
                        self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                self.close_connection = True
                controller.unsubscribe(subscriber)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(page)
                return
            if parsed.path == "/api/events":
                query_token = parse_qs(parsed.query).get("token", [""])[0]
                if not secrets.compare_digest(query_token, token):
                    self._json({"error": "unauthorized"}, HTTPStatus.FORBIDDEN)
                    return
                self._events()
                return
            if not self._authorized():
                self._json({"error": "unauthorized"}, HTTPStatus.FORBIDDEN)
                return
            if parsed.path == "/api/status":
                self._json(controller.status())
                return
            if parsed.path == "/api/logs":
                query = parse_qs(parsed.query)
                try:
                    after = int(query.get("after", ["0"])[0])
                except ValueError:
                    after = 0
                self._json({"logs": controller.logs_after(after)})
                return
            if parsed.path == "/api/settings":
                self._json(controller.settings())
                return
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            if not self._authorized():
                self._json({"error": "unauthorized"}, HTTPStatus.FORBIDDEN)
                return
            if self.path == "/api/start":
                ok, message = controller.start()
                self._json({"ok": ok, "message": message})
                return
            if self.path == "/api/pause":
                ok, message = controller.pause()
                self._json({"ok": ok, "message": message})
                return
            if self.path == "/api/settings":
                try:
                    controller.update_settings(self._read_json())
                except ValueError as exc:
                    self._json(
                        {"ok": False, "error": str(exc)},
                        HTTPStatus.BAD_REQUEST,
                    )
                    return
                self._json({"ok": True})
                return
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

    return Handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vita Gamepad 图形控制面板")
    parser.add_argument(
        "--backend", choices=("auto", "windows", "macos", "debug"), default="auto"
    )
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--discovery-port", type=int, default=5001)
    parser.add_argument("--allow")
    parser.add_argument("--timeout-ms", type=int, default=300)
    parser.add_argument("--ui-port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--config", help="按键映射 JSON 配置文件路径")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    controller = DashboardController(
        backend_name=args.backend,
        bind=args.bind,
        port=args.port,
        discovery_port=args.discovery_port,
        allow=args.allow,
        timeout_ms=args.timeout_ms,
        config_path=args.config,
    )
    token = secrets.token_urlsafe(24)
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.ui_port), make_handler(controller, token)
    )
    server.daemon_threads = True
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Vita Gamepad 控制面板：{url}")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        controller.pause()
        server.server_close()


if __name__ == "__main__":
    main()
