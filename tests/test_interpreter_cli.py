"""Проверки CLI интерпретатора и копирования массива через реальные файлы."""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COPY_CSV = PROJECT_ROOT / "examples" / "copy_array.csv"
SOURCE_START = 256
DESTINATION_START = 288
PROGRAM_START = 0
WORD_SIZE = 4
EXPECTED_ARRAY = [17, 1024, 0, 262143, 255]
SUCCESS = 0
RUNTIME_ERROR = 1
ARGUMENT_ERROR = 2


def run_interpreter(
    program: Path, dump: Path, start: int, end: int
) -> subprocess.CompletedProcess:
    """Запустить CLI штатной командой и захватить вывод."""
    return subprocess.run(
        [
            sys.executable, "-B", "-m", "src.interpreter",
            str(program), str(dump), str(start), str(end),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


class InterpreterCliTests(unittest.TestCase):
    """Проверки границ JSON-дампа, ошибок и копирования массива."""

    def setUp(self) -> None:
        """Выделить временные пути для программы и JSON-дампа."""
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.workdir = Path(directory.name)
        self.program = self.workdir / "input program.bin"
        self.dump_file = self.workdir / "output memory.dump.json"

    def test_copy_array_from_csv(self) -> None:
        """Исполнить пример и сравнить оба массива и сохранённый код."""
        assembler = subprocess.run(
            [str(PROJECT_ROOT / "run.sh"), str(COPY_CSV), str(self.program)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(assembler.returncode, SUCCESS, assembler.stderr)
        width = WORD_SIZE * len(EXPECTED_ARRAY)
        end = DESTINATION_START + width - 1
        result = run_interpreter(
            self.program, self.dump_file, PROGRAM_START, end
        )
        self.assertEqual(result.returncode, SUCCESS, result.stderr)
        dump = json.loads(self.dump_file.read_text(encoding="utf-8"))

        expected = b"".join(
            value.to_bytes(WORD_SIZE, "little") for value in EXPECTED_ARRAY
        )
        contents = bytes(dump["memory"])
        program = self.program.read_bytes()
        self.assertLessEqual(len(program), SOURCE_START)
        self.assertEqual(dump["start"], PROGRAM_START)
        self.assertEqual(dump["end"], end)
        self.assertEqual(len(contents), end - PROGRAM_START + 1)
        self.assertEqual(contents[:len(program)], program)
        self.assertEqual(contents[SOURCE_START:SOURCE_START + width], expected)
        self.assertEqual(contents[DESTINATION_START:], expected)

    def test_single_byte_range(self) -> None:
        """Сохранить ровно один байт по заданному ненулевому адресу."""
        self.program.write_bytes(bytes.fromhex("60 A1 10 00 00"))
        result = run_interpreter(self.program, self.dump_file, 1, 1)
        self.assertEqual(result.returncode, SUCCESS, result.stderr)
        data = json.loads(self.dump_file.read_text(encoding="utf-8"))
        self.assertEqual(data, {"start": 1, "end": 1, "memory": [161]})

    def test_invalid_range(self) -> None:
        """Отклонить неверный диапазон до чтения и записи файлов."""
        result = run_interpreter(self.program, self.dump_file, 8, 7)
        self.assertEqual(result.returncode, ARGUMENT_ERROR)
        self.assertIn("диапазон", result.stderr)
        self.assertFalse(self.dump_file.exists())

    def test_missing_binary(self) -> None:
        """Сообщить об ошибке чтения при отсутствии бинарного файла."""
        result = run_interpreter(self.program, self.dump_file, 0, 0)
        self.assertEqual(result.returncode, RUNTIME_ERROR)
        self.assertIn("Ошибка чтения", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(self.dump_file.exists())

    def test_execution_error_preserves_dump(self) -> None:
        """Оставить прежний дамп при ошибке исполнения программы."""
        self.program.write_bytes(bytes.fromhex("20 00 00 00 00 3F 00 00 00 00"))
        self.dump_file.write_text("previous", encoding="utf-8")
        result = run_interpreter(self.program, self.dump_file, 0, 9)
        self.assertEqual(result.returncode, RUNTIME_ERROR)
        self.assertIn("адрес команды 5", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.dump_file.read_text(encoding="utf-8"), "previous")

    def test_write_error(self) -> None:
        """Выдать понятную ошибку при недоступном выходном пути."""
        self.program.write_bytes(bytes.fromhex("20 00 00 00 00"))
        result = run_interpreter(self.program, self.workdir, 0, 0)
        self.assertEqual(result.returncode, RUNTIME_ERROR)
        self.assertIn("Ошибка записи", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_same_input_and_output(self) -> None:
        """Защитить исходную бинарную программу от замены JSON-дампом."""
        code = bytes.fromhex("20 00 00 00 00")
        self.program.write_bytes(code)
        result = run_interpreter(self.program, self.program, 0, 0)
        self.assertEqual(result.returncode, RUNTIME_ERROR)
        self.assertIn("совпадают", result.stderr)
        self.assertEqual(self.program.read_bytes(), code)
