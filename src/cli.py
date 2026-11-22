"""Интерфейс командной строки ассемблера УВМ."""

import argparse
import sys
from pathlib import Path
from typing import Optional

from assembler import AssemblyError, parse_program


def create_parser() -> argparse.ArgumentParser:
    """Описать два обязательных пути и флаг тестового режима."""
    parser = argparse.ArgumentParser(
        prog="run.sh",
        description="Ассемблер УВМ, вариант 20. Этап 1.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "source", metavar="SOURCE", type=Path, help="путь к исходному CSV"
    )
    parser.add_argument(
        "output",
        metavar="OUTPUT",
        type=Path,
        help="путь к бинарному результату (запись появится на этапе 2)",
    )
    parser.add_argument(
        "-t", "--test", action="store_true", help="вывести поля команд"
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Прочитать CSV и вывести поля команд при включённом режиме проверки."""
    args = create_parser().parse_args(argv)
    try:
        with args.source.open(encoding="utf-8-sig", newline="") as source:
            instructions = parse_program(source)
    except UnicodeDecodeError:
        print(
            f"Ошибка: {args.source}: ожидается кодировка UTF-8",
            file=sys.stderr,
        )
        return 1
    except AssemblyError as exc:
        print(f"Ошибка: {args.source}: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Ошибка чтения: {exc}", file=sys.stderr)
        return 1

    if args.test:
        for instruction in instructions:
            print(instruction.format_fields())
    return 0


if __name__ == "__main__":
    sys.exit(main())
