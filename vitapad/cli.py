from __future__ import annotations

import argparse
import sys

from vitapad.backends import create_backend
from vitapad.receiver import Receiver


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vitapad", description="将 PSVita 输入转换为电脑虚拟游戏手柄"
    )
    parser.add_argument(
        "--backend", choices=("auto", "windows", "macos", "debug"), default="auto"
    )
    parser.add_argument("--bind", default="0.0.0.0", help="UDP 监听地址")
    parser.add_argument("--port", type=int, default=5000, help="输入端口")
    parser.add_argument(
        "--discovery-port", type=int, default=5001, help="自动发现广播端口"
    )
    parser.add_argument("--allow", metavar="IP", help="只接受指定 PSVita IP")
    parser.add_argument(
        "--timeout-ms", type=int, default=300, help="断线释放按键时间"
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not 1 <= args.port <= 65535 or not 1 <= args.discovery_port <= 65535:
        raise SystemExit("端口必须在 1 到 65535 之间")
    if not 50 <= args.timeout_ms <= 10000:
        raise SystemExit("--timeout-ms 必须在 50 到 10000 之间")
    try:
        backend = create_backend(args.backend)
        receiver = Receiver(
            backend=backend,
            bind=args.bind,
            port=args.port,
            discovery_port=args.discovery_port,
            allow=args.allow,
            timeout_ms=args.timeout_ms,
        )
        receiver.run()
    except KeyboardInterrupt:
        print("\n已停止")
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

