"""Проверки декодирования и исполнения машинного кода УВМ."""

import unittest

from src.assembler import (
    AssemblyError,
    Instruction,
    decode_instruction,
    encode_program,
    parse_program,
)
from src.vm import MEMORY_SIZE, ExecutionError, VirtualMachine


class DecoderTests(unittest.TestCase):
    """Эталоны PDF, границы полей и недопустимое кодирование."""

    def test_reference_instructions(self) -> None:
        """Декодировать все четыре команды из спецификации."""
        examples = (
            ("60 A1 10 00 00", Instruction(32, 5, 532)),
            ("7E B6 0B 00 00", Instruction(62, 25, 22, 11)),
            ("B5 BA 00 00 00", Instruction(53, 10, 23)),
            ("64 67 00 00 00", Instruction(36, 29, 12)),
            ("E0 FF FF 1F 00", Instruction(32, 31, 262143)),
            ("FE FF 1F 00 00", Instruction(62, 31, 31, 31)),
        )
        for code, expected in examples:
            with self.subTest(code=code):
                command = decode_instruction(bytes.fromhex(code))
                self.assertEqual(command, expected)

    def test_invalid_encoding(self) -> None:
        """Обнаружить неверный размер, код операции и резервные биты."""
        examples = (
            ("", "размер команды"),
            ("20 00 00 00", "размер команды"),
            ("20 00 00 00 00 00", "размер команды"),
            ("3F 00 00 00 00", "поле A"),
            ("20 00 00 20 00", "резервные биты"),
            ("3E 00 20 00 00", "резервные биты"),
            ("35 00 01 00 00", "резервные биты"),
            ("24 00 00 00 01", "резервные биты"),
        )
        for code, error in examples:
            with self.subTest(code=code):
                with self.assertRaisesRegex(AssemblyError, error):
                    decode_instruction(bytes.fromhex(code))


def make_vm(*lines: str) -> VirtualMachine:
    """Собрать команды CSV и загрузить их в УВМ."""
    return VirtualMachine(encode_program(parse_program(lines)))


class VirtualMachineTests(unittest.TestCase):
    """Проверки инструкций, одной памяти и границ адресов."""

    def test_load_read_and_write(self) -> None:
        """Сохранить константу, прочитать её со смещением и записать копию."""
        machine = make_vm(
            "load,r31,262143",
            "load,r2,120",
            "write,r31,r2",
            "load,r2,116",
            "read,r2,r31,4",
            "load,r2,124",
            "write,r31,r2",
        )
        machine.run()
        self.assertEqual(machine.dump(120, 127), [255, 255, 3, 0] * 2)

    def test_read_from_instruction_memory(self) -> None:
        """Прочитать первые байты кода обычной командой чтения данных."""
        machine = make_vm("read,r0,r31,0", "load,r1,100", "write,r31,r1")
        machine.run()
        self.assertEqual(machine.dump(100, 103), [0x3E, 0xF8, 0, 0])

    def test_fetch_observes_memory_write(self) -> None:
        """Выбрать изменённую инструкцию из той же памяти, куда пишет write."""
        machine = make_vm(
            "load,r1,202976",
            "load,r2,15",
            "write,r1,r2",
            "load,r3,1",
            "load,r4,100",
            "write,r3,r4",
        )
        machine.run()
        self.assertEqual(machine.dump(15, 19), [0xE0, 0x18, 0x03, 0, 0])
        self.assertEqual(machine.dump(100, 103), [99, 0, 0, 0])

    def test_unaligned_read_preserves_full_word(self) -> None:
        """Сохранить старший байт значения, прочитанного без выравнивания."""
        machine = make_vm(
            "load,r0,100",
            "load,r1,255",
            "load,r2,104",
            "write,r1,r2",
            "read,r0,r1,1",
            "load,r2,112",
            "write,r1,r2",
        )
        machine.run()
        self.assertEqual(machine.dump(112, 115), [0, 0, 0, 255])

    def test_last_word_in_memory(self) -> None:
        """Прочитать и записать слово, заканчивающееся последним байтом."""
        machine = make_vm(
            "load,r0,262140",
            "load,r1,261",
            "write,r1,r0",
            "read,r0,r2,0",
            "load,r0,100",
            "write,r2,r0",
        )
        machine.run()
        self.assertEqual(machine.dump(262140, 262143), [5, 1, 0, 0])
        self.assertEqual(machine.dump(100, 103), [5, 1, 0, 0])

    def test_word_crosses_memory_end(self) -> None:
        """Отклонить слово с допустимым началом и недопустимым концом."""
        for instruction in ("read,r0,r1,0", "write,r1,r0"):
            with self.subTest(instruction=instruction):
                machine = make_vm("load,r0,262141", "load,r1,9", instruction)
                with self.assertRaisesRegex(ExecutionError, r"262141"):
                    machine.run()
                self.assertEqual(machine.dump(262141, 262143), [0, 0, 0])

    def test_base_and_displacement_cross_memory_end(self) -> None:
        """Проверить границу вычисленного адреса после прибавления D."""
        machine = make_vm("load,r0,262143", "read,r0,r1,1")
        with self.assertRaisesRegex(ExecutionError, r"262144"):
            machine.run()

    def test_invalid_dump_ranges(self) -> None:
        """Отклонить отрицательный, обратный и слишком широкий диапазоны."""
        machine = make_vm("load,r0,1")
        for start, end in ((-1, 0), (1, 0), (0, MEMORY_SIZE)):
            with self.subTest(start=start, end=end):
                with self.assertRaisesRegex(ExecutionError, "диапазон"):
                    machine.dump(start, end)

    def test_invalid_program_length(self) -> None:
        """Отклонить пустой, обрезанный и слишком большой бинарный файл."""
        examples = (
            (b"", "пустая"),
            (bytes.fromhex("20 00 00 00 00 01"), "кратен"),
            (bytes(MEMORY_SIZE + 1), "превышает"),
        )
        for program, error in examples:
            with self.subTest(size=len(program)):
                with self.assertRaisesRegex(ExecutionError, error):
                    VirtualMachine(program)

    def test_invalid_opcode_reports_instruction_address(self) -> None:
        """Указать адрес ошибочной команды после корректной инструкции."""
        machine = VirtualMachine(bytes.fromhex("20 00 00 00 00 3F 00 00 00 00"))
        message = r"адрес команды 5:.*поле A"
        with self.assertRaisesRegex(ExecutionError, message):
            machine.run()

    def test_popcnt_requires_stage_four(self) -> None:
        """Сообщить об этапе 4 при исполнении корректной команды popcnt."""
        machine = make_vm("load,r0,1", "popcnt,r0,r1")
        with self.assertRaisesRegex(ExecutionError, r"popcnt.*этапе 4"):
            machine.run()
