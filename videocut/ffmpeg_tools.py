"""Project entry point for the pinned, unmodified ffmpeg-skill tools."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def parse_json_output(stdout: str) -> dict:
    """The look tool prints declared output paths after its JSON document."""
    source = stdout.lstrip()
    doc, end = json.JSONDecoder().raw_decode(source)
    if not isinstance(doc, dict):
        raise TypeError("Expected a JSON object from videocut ffmpeg")
    trailing = [line.strip() for line in source[end:].splitlines() if line.strip()]
    if any(line not in doc.get("outputs", []) for line in trailing):
        raise ValueError("Unexpected non-JSON tool output")
    return doc


def invoke_json(arguments: list[str], *, report: Path | None = None) -> dict:
    """Call the pinned tools without a shell; preserve raw evidence if requested."""
    result = subprocess.run(
        [sys.executable, "-m", "videocut.ffmpeg_tools", *map(str, arguments)],
        capture_output=True, text=True, check=False,
    )
    if report:
        report.with_name(report.name + ".stdout").write_text(result.stdout)
        report.with_name(report.name + ".stderr").write_text(result.stderr)
    if result.returncode:
        raise RuntimeError(f"videocut ffmpeg {arguments[0]} failed ({result.returncode}): {result.stderr[-1800:]}")
    doc = parse_json_output(result.stdout)
    if report:
        report.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    return doc


def skill_directory() -> Path:
    package = Path(__file__).resolve().parent
    for directory in (
        package.parent / ".agents/skills/ffmpeg-skill",
        package / "_vendor/ffmpeg_skill",
    ):
        if (directory / "SKILL.md").is_file():
            return directory
    raise RuntimeError("The bundled ffmpeg-skill is missing; restore the project files")


def main(argv: list[str] | None = None) -> int:
    directory = skill_directory()
    tools = sorted(
        path.stem
        for path in (directory / "scripts").glob("*.py")
        if not path.name.startswith("_")
    )
    parser = argparse.ArgumentParser(
        prog="videocut ffmpeg",
        description="Local ffmpeg-skill tools; use TOOL --help for upstream arguments",
    )
    parser.add_argument("--list", action="store_true", help="List available tools")
    parser.add_argument(
        "tool",
        nargs="?",
        default="list",
        choices=["list", "doctor", "contract", *tools],
    )
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.list or args.tool == "list":
        print("\n".join(["doctor", "contract", *tools]))
        return 0
    if args.tool in {"doctor", "contract"}:
        script = directory / "scripts/_contract.py"
        arguments = ["doctor"] if args.tool == "doctor" else []
    else:
        script = directory / "scripts" / f"{args.tool}.py"
        arguments = []
    # Keep the caller's cwd and argument boundaries: media paths, JSON, error codes,
    # timeouts and overwrite protection belong to the upstream tool.
    try:
        return subprocess.call(
            [sys.executable, str(script), *arguments, *args.arguments]
        )
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
