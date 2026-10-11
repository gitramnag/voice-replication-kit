#!/usr/bin/env python3
"""Run a hash-verified private CosyVoice 3 zero-shot request pack."""
from __future__ import annotations

import argparse
from pathlib import Path

from voice_replication_kit.cli import _render_command


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root containing the reviewed public configs/pins.json",
    )
    parser.add_argument("--private-root", type=Path)
    parser.add_argument("--requests", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--request-id")
    parser.add_argument("--smoke", "--smoke-only", dest="smoke", action="store_true")
    parser.add_argument("--accept-smoke")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument(
        "--max-batch-seconds",
        "--max-seconds",
        dest="max_batch_seconds",
        type=float,
        default=8 * 60 * 60,
        help="stop between inference calls after this batch wall-clock limit",
    )
    parser.add_argument("--precision", choices=("fp16", "fp32"), default="fp16")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return _render_command(args, repository_root=args.root.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
