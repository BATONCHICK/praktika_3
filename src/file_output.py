"""Общая запись выходных файлов ассемблера и интерпретатора."""

import os
import stat
import tempfile
from pathlib import Path


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


def write_output(source: Path, output: Path, data: bytes) -> None:
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
            stream.write(data)
        temporary.replace(output)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
