"""Проверки запуска ассемблера обоих этапов через run.sh."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_SCRIPT = PROJECT_ROOT / "run.sh"
REFERENCE_CSV = PROJECT_ROOT / "examples" / "references.csv"
REFERENCE_FIELDS = (
    "A=32, B=5, C=532\n"
    "A=62, B=25, C=22, D=11\n"
    "A=53, B=10, C=23\n"
    "A=36, B=29, C=12\n"
)
REFERENCE_BYTES = bytes.fromhex(
    "60 A1 10 00 00 7E B6 0B 00 00 B5 BA 00 00 00 64 67 00 00 00"
)
REFERENCE_SIZE = 20
REFERENCE_SIZE_OUTPUT = "Размер бинарного файла: 20 байт\n"
REFERENCE_HEX = (
    "0x60, 0xA1, 0x10, 0x00, 0x00\n"
    "0x7E, 0xB6, 0x0B, 0x00, 0x00\n"
    "0xB5, 0xBA, 0x00, 0x00, 0x00\n"
    "0x64, 0x67, 0x00, 0x00, 0x00\n"
)
SUCCESS_CODE = 0
ASSEMBLY_ERROR_CODE = 1
ARGUMENT_ERROR_CODE = 2


def run_cli(
    *arguments: str, cwd: Path = PROJECT_ROOT
) -> subprocess.CompletedProcess:
    """Запустить реальный CLI и сохранить код выхода и оба потока."""
    return subprocess.run(
        ["sh", str(RUN_SCRIPT), *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


class CliTests(unittest.TestCase):
    """Проверки интерфейса, кодов завершения и выходного пути."""

    def setUp(self) -> None:
        """Подготовить входные и выходные пути с пробелами."""
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.workdir = Path(temp_dir.name)
        self.source = self.workdir / "input file.csv"
        self.output = self.workdir / "output file.bin"

    def test_fields_mode(self) -> None:
        """Вывести эталонные поля этапа 1 без создания бинарного файла."""
        result = run_cli(str(REFERENCE_CSV), str(self.output), "--fields")
        self.assertEqual(result.returncode, SUCCESS_CODE, result.stderr)
        self.assertEqual(result.stdout, REFERENCE_FIELDS)
        self.assertEqual(result.stderr, "")
        self.assertFalse(self.output.exists())

    def test_reference_machine_code(self) -> None:
        """Записать 20 точных байтов и показать их в формате PDF."""
        result = run_cli(str(REFERENCE_CSV), str(self.output), "--test")
        self.assertEqual(result.returncode, SUCCESS_CODE, result.stderr)
        self.assertEqual(result.stdout, REFERENCE_SIZE_OUTPUT + REFERENCE_HEX)
        self.assertEqual(result.stderr, "")
        self.assertEqual(self.output.stat().st_size, REFERENCE_SIZE)
        self.assertEqual(self.output.read_bytes(), REFERENCE_BYTES)

    def test_regular_mode_replaces_existing_output(self) -> None:
        """Заменить прежний файл целиком и напечатать только размер."""
        self.output.write_bytes(b"existing file with extra bytes")
        result = run_cli(str(REFERENCE_CSV), str(self.output))
        self.assertEqual(result.returncode, SUCCESS_CODE, result.stderr)
        self.assertEqual(result.stdout, REFERENCE_SIZE_OUTPUT)
        self.assertEqual(self.output.read_bytes(), REFERENCE_BYTES)

    def test_invalid_source_has_no_partial_stdout(self) -> None:
        """На ошибочном входе вывести диагностику, но не часть программы."""
        self.source.write_text("load,r1,0\nread,r1,r2,32\n", encoding="utf-8")
        result = run_cli(str(self.source), str(self.output), "--test")
        self.assertEqual(result.returncode, ASSEMBLY_ERROR_CODE)
        self.assertEqual(result.stdout, "")
        self.assertIn("строка 2", result.stderr)
        self.assertIn("поле D", result.stderr)
        self.assertFalse(self.output.exists())

    def test_regular_mode_rejects_invalid_program(self) -> None:
        """Сохранить прежний выходной файл при ошибке разбора CSV."""
        self.source.write_text("invalid\n", encoding="utf-8")
        self.output.write_bytes(b"existing")
        result = run_cli(str(self.source), str(self.output))
        self.assertEqual(result.returncode, ASSEMBLY_ERROR_CODE)
        self.assertIn("invalid", result.stderr)
        self.assertEqual(self.output.read_bytes(), b"existing")

    def test_missing_input(self) -> None:
        """Обработать отсутствие входного файла без трассировки Python."""
        result = run_cli(str(self.source), str(self.output), "--test")
        self.assertEqual(result.returncode, ASSEMBLY_ERROR_CODE)
        self.assertIn(self.source.name, result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_invalid_encoding(self) -> None:
        """Вывести понятную диагностику при неверной кодировке файла."""
        self.source.write_bytes(b"\xff\xfe")
        result = run_cli(str(self.source), str(self.output))
        self.assertEqual(result.returncode, ASSEMBLY_ERROR_CODE)
        self.assertIn("UTF-8", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_relative_paths_outside_project(self) -> None:
        """Запустить CLI из другой папки и прочитать CSV с BOM и CRLF."""
        self.source.write_bytes(b"\xef\xbb\xbfread,r0,r1,0\r\n")
        result = run_cli(
            self.source.name, self.output.name, "-t", cwd=self.workdir
        )
        self.assertEqual(result.returncode, SUCCESS_CODE, result.stderr)
        self.assertEqual(
            result.stdout,
            "Размер бинарного файла: 5 байт\n0x3E, 0x08, 0x00, 0x00, 0x00\n",
        )
        self.assertEqual(
            self.output.read_bytes(), bytes.fromhex("3E 08 00 00 00")
        )

    def test_rejects_invalid_output_path(self) -> None:
        """Сообщить об ошибке записи для каталога и отсутствующего родителя."""
        for output in (self.workdir, self.workdir / "missing" / "output.bin"):
            with self.subTest(output=output):
                result = run_cli(str(REFERENCE_CSV), str(output), "--test")
                self.assertEqual(result.returncode, ASSEMBLY_ERROR_CODE)
                self.assertEqual(result.stdout, "")
                self.assertIn("Ошибка записи", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(list(self.workdir.iterdir()), [])

    def test_rejects_read_only_output(self) -> None:
        """Сохранить защищённый файл и сообщить об отказе записи."""
        self.output.write_bytes(b"existing")
        self.output.chmod(0o400)
        if os.access(self.output, os.W_OK):
            self.skipTest("пользователь может писать в файл с режимом 0400")
        result = run_cli(str(REFERENCE_CSV), str(self.output))
        self.assertEqual(result.returncode, ASSEMBLY_ERROR_CODE)
        self.assertIn("Ошибка записи", result.stderr)
        self.assertEqual(self.output.read_bytes(), b"existing")

    def test_refuses_to_overwrite_source(self) -> None:
        """Сохранить CSV при совпадении путей, включая файловые ссылки."""
        original = b"load,r1,0\n"
        self.source.write_bytes(original)
        symlink = self.workdir / "symlink.bin"
        symlink.symlink_to(self.source)
        hardlink = self.workdir / "hardlink.bin"
        os.link(self.source, hardlink)
        for output in (self.source, symlink, hardlink):
            with self.subTest(output=output):
                result = run_cli(str(self.source), str(output), "--test")
                self.assertEqual(result.returncode, ASSEMBLY_ERROR_CODE)
                self.assertEqual(result.stdout, "")
                self.assertIn("совпадают", result.stderr)
                self.assertEqual(output.read_bytes(), original)

    def test_modes_are_mutually_exclusive(self) -> None:
        """Отклонить одновременный запрос двух режимов демонстрации."""
        result = run_cli(
            str(REFERENCE_CSV), str(self.output), "--fields", "--test"
        )
        self.assertEqual(result.returncode, ARGUMENT_ERROR_CODE)
        self.assertFalse(self.output.exists())

    def test_requires_output_argument(self) -> None:
        """Вернуть код ошибки CLI при пропущенном выходном пути."""
        result = run_cli(str(REFERENCE_CSV), "--test")
        self.assertEqual(result.returncode, ARGUMENT_ERROR_CODE)
        self.assertIn("OUTPUT", result.stderr)

    def test_help(self) -> None:
        """Показать оба пути и аргумент тестового режима."""
        result = run_cli("--help")
        self.assertEqual(result.returncode, SUCCESS_CODE, result.stderr)
        for argument in ("SOURCE", "OUTPUT", "--test", "--fields"):
            self.assertIn(argument, result.stdout)
