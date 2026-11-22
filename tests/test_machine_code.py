"""Проверки побайтового кодирования команд варианта 20."""

import unittest
from pathlib import Path

from src.assembler import (
    AssemblyError,
    Instruction,
    encode_instruction,
    encode_program,
    parse_program,
)


REFERENCE_CSV = Path(__file__).resolve().parents[1] / "examples/references.csv"
REFERENCE_CODE = "60 A1 10 00 00 7E B6 0B 00 00 B5 BA 00 00 00 64 67 00 00 00"


class MachineCodeTests(unittest.TestCase):
    """Эталоны из PDF, крайние значения и ошибки кодирования."""

    def test_reference_instructions(self) -> None:
        """Сверить код каждой из четырёх команд с отдельным эталоном."""
        cases = (
            (Instruction(32, 5, 532), "60 A1 10 00 00"),
            (Instruction(62, 25, 22, 11), "7E B6 0B 00 00"),
            (Instruction(53, 10, 23), "B5 BA 00 00 00"),
            (Instruction(36, 29, 12), "64 67 00 00 00"),
        )
        for instruction, expected in cases:
            with self.subTest(instruction=instruction):
                self.assertEqual(
                    encode_instruction(instruction), bytes.fromhex(expected)
                )

    def test_reference_csv(self) -> None:
        """Проверить точный порядок и длину байтов эталонной программы."""
        with REFERENCE_CSV.open(encoding="utf-8", newline="") as source:
            instructions = parse_program(source)
        self.assertEqual(
            encode_program(instructions), bytes.fromhex(REFERENCE_CODE)
        )

    def test_operand_boundaries(self) -> None:
        """При заполнении поля не затронуть соседние и резервные биты."""
        cases = (
            (Instruction(32, 0, 0), "20 00 00 00 00"),
            (Instruction(32, 31, 0), "E0 07 00 00 00"),
            (Instruction(32, 0, 262143), "20 F8 FF 1F 00"),
            (Instruction(32, 31, 262143), "E0 FF FF 1F 00"),
            (Instruction(62, 0, 0, 0), "3E 00 00 00 00"),
            (Instruction(62, 0, 31, 0), "3E F8 00 00 00"),
            (Instruction(62, 0, 0, 31), "3E 00 1F 00 00"),
            (Instruction(62, 31, 31, 31), "FE FF 1F 00 00"),
            (Instruction(53, 0, 0), "35 00 00 00 00"),
            (Instruction(53, 31, 31), "F5 FF 00 00 00"),
            (Instruction(36, 0, 0), "24 00 00 00 00"),
            (Instruction(36, 31, 31), "E4 FF 00 00 00"),
        )
        for instruction, expected in cases:
            with self.subTest(instruction=instruction):
                self.assertEqual(
                    encode_instruction(instruction), bytes.fromhex(expected)
                )

    def test_rejects_invalid_instruction(self) -> None:
        """Отклонить неизвестный код, лишние поля и неверные операнды."""
        cases = (
            (Instruction(0, 0, 0), "поле A"),
            (Instruction(64, 0, 0), "поле A"),
            (Instruction(32, 32, 0), "поле B"),
            (Instruction(32, -1, 0), "поле B"),
            (Instruction(32, False, 0), "поле B"),
            (Instruction(32, 0, 262144), "поле C"),
            (Instruction(53, 0, 32), "поле C"),
            (Instruction(36, 0, 0, 0), "поле D"),
            (Instruction(62, 0, 0), "поле D"),
            (Instruction(62, 0, 0, -1), "поле D"),
            (Instruction(62, 0, 0, 32), "поле D"),
        )
        for instruction, error in cases:
            with self.subTest(instruction=instruction):
                with self.assertRaisesRegex(AssemblyError, error):
                    encode_instruction(instruction)
