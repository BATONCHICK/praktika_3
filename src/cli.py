"""Интерфейс командной строки ассемблера УВМ."""

import argparse
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Optional

from assembler import (
    INSTRUCTION_SIZE,
    AssemblyError,
    encode_program,
    parse_program,
)


def create_parser() -> argparse.ArgumentParser:
    """Описать обязательные пути и два режима демонстрации."""
    parser = argparse.ArgumentParser(
        prog="run.sh",
        description="Ассемблер УВМ, вариант 20.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "source", metavar="SOURCE", type=Path, help="путь к исходному CSV"
    )
    parser.add_argument(
        "output", metavar="OUTPUT", type=Path, help="путь к бинарному файлу"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "-t", "--test", action="store_true", help="вывести байты команд"
    )
    mode.add_argument(
        "--fields", action="store_true", help="вывести поля команд без записи"
    )
    return parser


def _check_destination(source: Path, output: Path) -> None:
    """Проверить, что существующий выходной файл пригоден для замены."""
    try:
        destination_stat = output.stat()
    except FileNotFoundError:
        return
    if not stat.S_ISREG(destination_stat.st_mode):
        raise OSError("выходной путь должен указывать на обычный файл")
    if os.path.samestat(source.stat(), destination_stat):
        raise OSError("входной и выходной файлы совпадают")
    if not os.access(output, os.W_OK):
        raise PermissionError("выходной файл недоступен для записи")


def _write_binary(source: Path, output: Path, code: bytes) -> None:
    """Записать байты во временный файл и заменить выходной файл целиком."""
    if output.is_symlink():
        output = output.resolve()
    _check_destination(source, output)

    stream = tempfile.NamedTemporaryFile(
        dir=output.parent, suffix=".bin", delete=False
    )
    temporary = Path(stream.name)
    try:
        with stream:
            stream.write(code)
        temporary.replace(output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _print_hex(code: bytes) -> None:
    """Вывести одну строку шестнадцатеричных байтов на команду."""
    for start in range(0, len(code), INSTRUCTION_SIZE):
        chunk = code[start:start + INSTRUCTION_SIZE]
        print(", ".join(f"0x{value:02X}" for value in chunk))


def main(argv: Optional[list[str]] = None) -> int:
    """Прочитать CSV и показать поля или записать машинный код."""
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

    if args.fields:
        for instruction in instructions:
            print(instruction.format_fields())
        return 0

    code = encode_program(instructions)
    try:
        _write_binary(args.source, args.output, code)
    except (OSError, RuntimeError) as exc:
        print(f"Ошибка записи: {args.output}: {exc}", file=sys.stderr)
        return 1

    print(f"Размер бинарного файла: {len(code)} байт")
    if args.test:
        _print_hex(code)
    return 0


if __name__ == "__main__":
    sys.exit(main())
