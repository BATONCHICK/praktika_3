"""Проверки трансляции CSV в промежуточное представление."""

import unittest
from pathlib import Path

from src.assembler import AssemblyError, Instruction, parse_program


REFERENCE_CSV = Path(__file__).resolve().parents[1] / "examples/references.csv"


class AssemblerTests(unittest.TestCase):
    """Проверки команд, границ полей и диагностики ошибок."""

    def test_reference_instructions(self) -> None:
        """Воспроизвести четыре эталона из спецификации УВМ."""
        with REFERENCE_CSV.open(encoding="utf-8", newline="") as source:
            program = parse_program(source)

        self.assertEqual(
            program,
            [
                Instruction(32, 5, 532),
                Instruction(62, 25, 22, 11),
                Instruction(53, 10, 23),
                Instruction(36, 29, 12),
            ],
        )

    def test_operand_boundaries(self) -> None:
        """Принять нули и наибольшие значения каждого поля."""
        program = parse_program(
            [
                "load,0,0\n",
                "load,31,262143\n",
                "read,0,0,0\n",
                "read,31,31,31\n",
                "write,0,31\n",
                "popcnt,31,0\n",
            ]
        )
        self.assertEqual(
            program,
            [
                Instruction(32, 0, 0),
                Instruction(32, 31, 262143),
                Instruction(62, 0, 0, 0),
                Instruction(62, 31, 31, 31),
                Instruction(53, 0, 31),
                Instruction(36, 31, 0),
            ],
        )

    def test_csv_quotes_and_spaces(self) -> None:
        """Распознать кавычки, пробелы, пустую строку и ведущие нули."""
        program = parse_program([' "LOAD", "r05", " 00532 "\n', "\n"])
        self.assertEqual(program, [Instruction(32, 5, 532)])

    def test_rejects_unknown_opcode(self) -> None:
        """Для неизвестной мнемоники указать команду и номер строки."""
        with self.assertRaisesRegex(AssemblyError, r"строка 2:.*jump"):
            parse_program(["load,r1,10\n", "jump,r1\n"])

    def test_rejects_wrong_operand_count(self) -> None:
        """Выявить лишние и пропущенные операнды."""
        for line in ("load,r1", "load,r1,0,0", "read,r1,r2", "write"):
            with self.subTest(line=line):
                with self.assertRaisesRegex(AssemblyError, r"операнд"):
                    parse_program([line])

    def test_rejects_invalid_operands(self) -> None:
        """Сообщить о неверном формате или выходе поля за диапазон."""
        cases = (
            ("load,r32,0", "B"),
            ("load,r-1,0", "B"),
            ("load,r1,262144", "C"),
            ("load,r1," + "9" * 5000, "C"),
            ("load,r1,-1", "C"),
            ("load,r1,1_000", "C"),
            ("load,r1,0x10", "C"),
            ("load,r1,１", "C"),
            ("load,r1,", "C"),
            ("read,r1,r32,0", "C"),
            ("read,r1,r2,32", "D"),
            ("read,r1,r2,r3", "D"),
            ("write,r1.5,r2", "B"),
            ("popcnt,r1,s2", "C"),
        )
        for line, field in cases:
            with self.subTest(case=line[:40]):
                with self.assertRaisesRegex(AssemblyError, f"поле {field}"):
                    parse_program([line])

    def test_rejects_malformed_csv(self) -> None:
        """Отличить повреждённые кавычки от ошибки в операнде."""
        for line in ('load,"r1,0', 'load,"r1"x,0'):
            with self.subTest(line=line):
                with self.assertRaisesRegex(AssemblyError, r"строка 2:.*CSV"):
                    parse_program(["\n", line])

    def test_rejects_empty_program(self) -> None:
        """Считать вход без команд ошибкой."""
        with self.assertRaisesRegex(AssemblyError, r"нет команд"):
            parse_program(["\n", "\n"])
