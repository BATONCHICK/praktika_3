"""Исполнение команд варианта 20 в единой байтовой памяти."""

from .assembler import (
    BYTE_ORDER,
    CONSTANT_BITS,
    INSTRUCTION_SIZE,
    LOAD_OPCODE,
    MAX_REGISTER,
    POPCNT_OPCODE,
    READ_OPCODE,
    WRITE_OPCODE,
    AssemblyError,
    Instruction,
    decode_instruction,
)


REGISTER_COUNT = MAX_REGISTER + 1
MEMORY_SIZE = 1 << CONSTANT_BITS
FIRST_ADDRESS = 0
LAST_ADDRESS = MEMORY_SIZE - 1
WORD_SIZE = 4
LAST_WORD_ADDRESS = MEMORY_SIZE - WORD_SIZE


class ExecutionError(ValueError):
    """Недопустимая программа, команда или адрес памяти УВМ."""


def validate_range(start: int, end: int) -> None:
    """Проверить включительный диапазон байтовых адресов."""
    if (
        type(start) is not int
        or type(end) is not int
        or not FIRST_ADDRESS <= start <= end <= LAST_ADDRESS
    ):
        raise ExecutionError(
            f"недопустимый диапазон {start}..{end}. "
            f"Требуется {FIRST_ADDRESS} <= START <= END <= {LAST_ADDRESS}"
        )


def _word_slice(address: int) -> slice:
    """Вернуть срез для слова, целиком помещающегося в память."""
    if not FIRST_ADDRESS <= address <= LAST_WORD_ADDRESS:
        raise ExecutionError(
            f"адрес {address} вне диапазона начала {WORD_SIZE}-байтового "
            f"слова {FIRST_ADDRESS}..{LAST_WORD_ADDRESS}"
        )
    return slice(address, address + WORD_SIZE)


class VirtualMachine:
    """Регистры, счётчик команд и общая память команд и данных."""

    def __init__(self, program: bytes) -> None:
        """Загрузить программу с адреса 0 в обнулённую память."""
        if not program:
            raise ExecutionError("пустая бинарная программа")
        if len(program) > MEMORY_SIZE:
            raise ExecutionError(
                f"размер программы превышает {MEMORY_SIZE} байт"
            )
        if len(program) % INSTRUCTION_SIZE:
            raise ExecutionError(
                f"размер программы должен быть кратен {INSTRUCTION_SIZE} байтам"
            )
        self._program_end = len(program)
        self._pc = FIRST_ADDRESS
        self._registers = [0] * REGISTER_COUNT
        self._memory = bytearray(MEMORY_SIZE)
        self._memory[FIRST_ADDRESS:self._program_end] = program

    def run(self) -> None:
        """Считывать и исполнять команды до конца загруженной программы."""
        while self._pc < self._program_end:
            next_pc = self._pc + INSTRUCTION_SIZE
            code = bytes(self._memory[self._pc:next_pc])
            try:
                self._execute(decode_instruction(code))
            except (AssemblyError, ExecutionError) as exc:
                message = f"адрес команды {self._pc}: {exc}"
                raise ExecutionError(message) from exc
            self._pc = next_pc

    def _execute(self, instruction: Instruction) -> None:
        """Выполнить базовую инструкцию по декодированным полям."""
        opcode = instruction.opcode
        operand_b = instruction.operand_b
        operand_c = instruction.operand_c

        if opcode == LOAD_OPCODE:
            self._registers[operand_b] = operand_c
        elif opcode == READ_OPCODE:
            offset = instruction.operand_d
            assert offset is not None
            address = self._registers[operand_b] + offset
            self._registers[operand_c] = int.from_bytes(
                self._memory[_word_slice(address)], byteorder=BYTE_ORDER
            )
        elif opcode == WRITE_OPCODE:
            address = self._registers[operand_c]
            value = self._registers[operand_b]
            self._memory[_word_slice(address)] = value.to_bytes(
                WORD_SIZE, byteorder=BYTE_ORDER
            )
        elif opcode == POPCNT_OPCODE:
            raise ExecutionError("команда popcnt() будет доступна на этапе 4")
        else:
            raise ExecutionError(f"код операции {opcode} не поддерживается")

    def dump(self, start: int, end: int) -> list[int]:
        """Вернуть байты диапазона от start до end включительно."""
        validate_range(start, end)
        return list(self._memory[start:end + 1])
