from __future__ import annotations

import argparse
import asyncio
import getpass
import json
from pathlib import Path
from typing import Any

from .scanner import SUPER_SCANNER, default_packet
from .simcom import SIMCOM
from .vault import VAULT


def _load_packet(path: str | None) -> dict[str, Any]:
    if path is None:
        return default_packet()
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise SystemExit("Scenario root must be a JSON object.")
    return value


async def _scan(args: argparse.Namespace) -> int:
    packet = _load_packet(args.scenario)
    if args.worlds:
        packet["worlds"] = args.worlds
    if args.seed is not None:
        packet["seed"] = args.seed
    packet["includeRemoteModels"] = bool(args.remote)
    report = await SUPER_SCANNER.scan(packet)
    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(rendered + "\n")
        print(f"Wrote {args.output}")
    else:
        print(rendered)
    return 0


async def _simcom(args: argparse.Namespace) -> int:
    if not args.command:
        raise SystemExit("Provide a SIMCOM command, for example: cyberforgectl simcom boot")
    packet = _load_packet(args.scenario) if args.scenario else None
    result = await SIMCOM.execute(" ".join(args.command), packet=packet)
    print("\n".join(result.lines))
    return 0 if result.ok else 2


def _vault(args: argparse.Namespace) -> int:
    if args.action == "status":
        print(VAULT.status())
        return 0
    password = getpass.getpass("Vault password: ")
    if args.action == "create":
        token = VAULT.create(password)
    else:
        token = VAULT.unlock(password)
    if args.action == "set-provider":
        provider = args.provider
        secret = getpass.getpass(f"{provider} API key/token: ")
        VAULT.set_secret(token, provider, secret)
        print(f"Stored {provider} in the encrypted vault.")
    else:
        print("Vault session created. Use the Flutter UI for normal operation.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cyberforgectl")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    scan = sub.add_parser("scan", help="Run an authorized scenario and emit JSON.")
    scan.add_argument("scenario", nargs="?", help="Scenario JSON; default is synthetic demo.")
    scan.add_argument("--worlds", type=int)
    scan.add_argument("--seed", type=int)
    scan.add_argument("--remote", action="store_true")
    scan.add_argument("--output", "-o")
    scan.set_defaults(handler=_scan)

    simcom = sub.add_parser("simcom", help="Run a safe SIMCOM command.")
    simcom.add_argument("--scenario")
    simcom.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="SIMCOM command and arguments, including command-local --flags.",
    )
    simcom.set_defaults(handler=_simcom)

    vault = sub.add_parser("vault", help="Manage the local provider vault.")
    vault.add_argument("action", choices=["status", "create", "unlock", "set-provider"])
    vault.add_argument("--provider", choices=["openai", "xai", "digitalocean", "gemini"], default="openai")
    vault.set_defaults(handler=_vault)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    handler = args.handler
    if asyncio.iscoroutinefunction(handler):
        raise SystemExit(asyncio.run(handler(args)))
    raise SystemExit(handler(args))


if __name__ == "__main__":
    main()
