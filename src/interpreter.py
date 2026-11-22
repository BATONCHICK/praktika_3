"""Интерфейс командной строки интерпретатора УВМ."""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .file_output import write_output
from .vm import MEMORY_SIZE, ExecutionError, VirtualMachine, validate_range


def create_parser() -> argparse.ArgumentParser:
    """Описать пути к файлам и включительный диапазон дампа."""
    parser = argparse.ArgumentParser(
        prog="python3 -m src.interpreter",
        description="Интерпретатор УВМ, вариант 20.",
        allow_abbrev=False,
    )
    parser.add_argument("program", metavar="PROGRAM", type=Path)
    parser.add_argument("dump", metavar="DUMP", type=Path, help="путь к JSON")
    parser.add_argument("start", metavar="START", type=int, help="первый адрес")
    parser.add_argument("end", metavar="END", type=int, help="последний адрес")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Загрузить программу, исполнить её и сохранить дамп в JSON."""
    parser = create_parser()
    args = parser.parse_args(argv)
    try:
        validate_range(args.start, args.end)
    except ExecutionError as exc:
        parser.error(str(exc))

    try:
        with args.program.open("rb") as stream:
            program = stream.read(MEMORY_SIZE + 1)
    except OSError as exc:
        print(f"Ошибка чтения: {exc}", file=sys.stderr)
        return 1

    try:
        machine = VirtualMachine(program)
        machine.run()
    except ExecutionError as exc:
        print(f"Ошибка исполнения: {exc}", file=sys.stderr)
        return 1

    dump = {
        "start": args.start,
        "end": args.end,
        "memory": machine.dump(args.start, args.end),
    }
    data = json.dumps(dump, indent=2) + "\n"
    try:
        write_output(args.program, args.dump, data.encode("utf-8"))
    except (OSError, RuntimeError) as exc:
        print(f"Ошибка записи: {args.dump}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
