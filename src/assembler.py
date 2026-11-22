"""Разбор CSV и кодирование команд УВМ варианта 20."""

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Optional


LOAD_OPCODE = 32
READ_OPCODE = 62
WRITE_OPCODE = 53
POPCNT_OPCODE = 36
INSTRUCTION_SIZE = 5
OPCODE_BITS = 6
REGISTER_BITS = 5
CONSTANT_BITS = 18
OFFSET_BITS = 5
MIN_OPERAND = 0
MAX_REGISTER = (1 << REGISTER_BITS) - 1
MAX_CONSTANT = (1 << CONSTANT_BITS) - 1
MAX_OFFSET = (1 << OFFSET_BITS) - 1
OPERAND_FIELDS = ("B", "C", "D")
OPERAND_B_SHIFT = OPCODE_BITS
OPERAND_C_SHIFT = OPERAND_B_SHIFT + REGISTER_BITS
OPERAND_D_SHIFT = OPERAND_C_SHIFT + REGISTER_BITS
OPERAND_SHIFTS = (OPERAND_B_SHIFT, OPERAND_C_SHIFT, OPERAND_D_SHIFT)


@dataclass(frozen=True)
class Instruction:
    """Код операции A, операнды B и C и необязательный операнд D."""

    opcode: int
    operand_b: int
    operand_c: int
    operand_d: Optional[int] = None

    def format_fields(self) -> str:
        """Вернуть поля команды в порядке и формате из спецификации."""
        fields = f"A={self.opcode}, B={self.operand_b}, C={self.operand_c}"
        if self.operand_d is not None:
            fields += f", D={self.operand_d}"
        return fields


class AssemblyError(ValueError):
    """Ошибка синтаксиса CSV или недопустимая команда УВМ."""


@dataclass(frozen=True)
class OperandSpec:
    """Верхняя граница поля и признак допустимого префикса регистра."""

    maximum: int
    is_register: bool = False


REGISTER = OperandSpec(MAX_REGISTER, is_register=True)
CONSTANT = OperandSpec(MAX_CONSTANT)
OFFSET = OperandSpec(MAX_OFFSET)
COMMANDS = {
    "load": (LOAD_OPCODE, (REGISTER, CONSTANT)),
    "read": (READ_OPCODE, (REGISTER, REGISTER, OFFSET)),
    "write": (WRITE_OPCODE, (REGISTER, REGISTER)),
    "popcnt": (POPCNT_OPCODE, (REGISTER, REGISTER)),
}
SPECS_BY_OPCODE = dict(COMMANDS.values())


def _parse_operand(token: str, field: str, spec: OperandSpec) -> int:
    """Преобразовать десятичный операнд и проверить границы поля."""
    token = token.strip()
    if spec.is_register:
        token = token.lower().removeprefix("r")
    if not token.isascii() or not token.isdecimal():
        raise AssemblyError(f"поле {field}: ожидалось целое число от 0")

    digits = token.lstrip("0") or "0"
    if len(digits) > len(str(spec.maximum)) or int(digits) > spec.maximum:
        raise AssemblyError(f"поле {field}: допустимо от 0 до {spec.maximum}")
    return int(digits)


def _parse_row(row: list[str]) -> Instruction:
    """Взять код операции и правила проверки операндов из таблицы команд."""
    mnemonic, *tokens = row
    mnemonic = mnemonic.strip().lower()
    command = COMMANDS.get(mnemonic)
    if command is None:
        raise AssemblyError(f"неизвестная команда {mnemonic!r}")

    opcode, specs = command
    if len(tokens) != len(specs):
        raise AssemblyError(
            f"команда {mnemonic!r}: ожидается операндов {len(specs)}, "
            f"получено {len(tokens)}"
        )
    operands = [
        _parse_operand(token, field, spec)
        for token, field, spec in zip(tokens, OPERAND_FIELDS, specs)
    ]
    return Instruction(opcode, *operands)


def parse_program(lines: Iterable[str]) -> list[Instruction]:
    """Разобрать CSV-программу целиком или сообщить номер ошибочной строки."""
    reader = csv.reader(lines, skipinitialspace=True, strict=True)
    instructions = []
    line_number = 1
    try:
        for row in reader:
            if row:
                instructions.append(_parse_row(row))
            line_number = reader.line_num + 1
    except csv.Error as exc:
        raise AssemblyError(
            f"строка {line_number}: неверный CSV ({exc})"
        ) from exc
    except AssemblyError as exc:
        raise AssemblyError(f"строка {line_number}: {exc}") from exc

    if not instructions:
        raise AssemblyError("во входном файле нет команд")
    return instructions


def encode_instruction(instruction: Instruction) -> bytes:
    """Проверить поля и упаковать команду в пять байтов little-endian."""
    opcode = instruction.opcode
    if type(opcode) is not int or opcode not in SPECS_BY_OPCODE:
        raise AssemblyError(f"поле A: неизвестный код операции {opcode!r}")
    specs = SPECS_BY_OPCODE[opcode]

    operands = (instruction.operand_b, instruction.operand_c)
    if instruction.operand_d is not None:
        operands += (instruction.operand_d,)
    if len(operands) != len(specs):
        raise AssemblyError(f"поле D: неверный набор полей для кода {opcode}")

    packed = opcode
    for value, spec, field, shift in zip(
        operands, specs, OPERAND_FIELDS, OPERAND_SHIFTS
    ):
        if type(value) is not int or not MIN_OPERAND <= value <= spec.maximum:
            raise AssemblyError(
                f"поле {field}: допустимо целое от {MIN_OPERAND} "
                f"до {spec.maximum}"
            )
        packed |= value << shift
    return packed.to_bytes(INSTRUCTION_SIZE, byteorder="little")


def encode_program(instructions: Iterable[Instruction]) -> bytes:
    """Объединить байты команд в порядке исходной программы."""
    return b"".join(
        encode_instruction(instruction) for instruction in instructions
    )
