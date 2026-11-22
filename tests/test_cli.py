"""Проверки запуска ассемблера через run.sh."""

import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_SCRIPT = PROJECT_ROOT / "run.sh"
REFERENCE_CSV = PROJECT_ROOT / "examples" / "references.csv"
REFERENCE_OUTPUT = (
    "A=32, B=5, C=532\n"
    "A=62, B=25, C=22, D=11\n"
    "A=53, B=10, C=23\n"
    "A=36, B=29, C=12\n"
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

    def test_reference_mode(self) -> None:
        """Вывести точные эталонные поля и оставить выходной путь пустым."""
        result = run_cli(str(REFERENCE_CSV), str(self.output), "--test")
        self.assertEqual(result.returncode, SUCCESS_CODE, result.stderr)
        self.assertEqual(result.stdout, REFERENCE_OUTPUT)
        self.assertEqual(result.stderr, "")
        self.assertFalse(self.output.exists())

    def test_regular_mode_preserves_existing_output(self) -> None:
        """Успешно проверить программу и сохранить существующий файл."""
        self.output.write_bytes(b"existing")
        result = run_cli(str(REFERENCE_CSV), str(self.output))
        self.assertEqual(result.returncode, SUCCESS_CODE, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.output.read_bytes(), b"existing")

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
        """Проверять содержание входного файла и в обычном режиме."""
        self.source.write_text("invalid\n", encoding="utf-8")
        result = run_cli(str(self.source), str(self.output))
        self.assertEqual(result.returncode, ASSEMBLY_ERROR_CODE)
        self.assertIn("invalid", result.stderr)

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
        self.assertEqual(result.stdout, "A=62, B=0, C=1, D=0\n")
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
        for argument in ("SOURCE", "OUTPUT", "--test"):
            self.assertIn(argument, result.stdout)
