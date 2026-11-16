from __future__ import annotations

import socket
import threading
import time
import unittest
from io import StringIO

from pymodbus.client import ModbusTcpClient

from modbus_app.config import AppConfig
from modbus_app.csv_import import format_reference_address, parse_csv, reference_to_offset
from modbus_app.random_values import format_register_range, parse_register_range, random_register_value
from modbus_app.server import DataModel, ModbusServerRunner


class DataModelTests(unittest.TestCase):
    def test_register_and_bit_values(self) -> None:
        model = DataModel(10)
        model.set("Holding Registers", 0, [1234, 0xFFFF])
        model.set("Coils", 9, [1])
        self.assertEqual(model.get("Holding Registers", 0, 2), [1234, 0xFFFF])
        self.assertEqual(model.get("Coils", 9), [True])


class CsvImportTests(unittest.TestCase):
    def test_standard_display_addresses_round_trip_to_offsets(self) -> None:
        expected = {
            "Coils": "00001",
            "Discrete Inputs": "10001",
            "Input Registers": "30001",
            "Holding Registers": "40001",
        }

        for data_type, reference in expected.items():
            with self.subTest(data_type=data_type):
                self.assertEqual(format_reference_address(data_type, 0), reference)
                self.assertEqual(reference_to_offset(data_type, reference), 0)

    def test_semicolon_csv_and_holding_register_references(self) -> None:
        stream = StringIO(
            "data_type;address;label;value\n"
            "Holding Registers;40001;Temperature;12\n"
            "Holding Registers;40403;Pressure;34\n"
        )

        records, skipped = parse_csv(stream, "Holding Registers")

        self.assertEqual(skipped, 0)
        self.assertEqual([record.address for record in records], [0, 402])
        self.assertEqual([record.value for record in records], [12, 34])

    def test_comma_csv_keeps_zero_based_addresses(self) -> None:
        stream = StringIO("data_type,address,label,value\nHolding Registers,12,Speed,1500\n")

        records, skipped = parse_csv(stream, "Holding Registers")

        self.assertEqual(skipped, 0)
        self.assertEqual(records[0].address, 12)

    def test_reference_ranges_follow_data_type(self) -> None:
        stream = StringIO(
            "data_type,address,value\n"
            "Coils,00001,1\n"
            "Discrete Inputs,10001,1\n"
            "Input Registers,30001,123\n"
        )

        records, skipped = parse_csv(stream, "Holding Registers")

        self.assertEqual(skipped, 0)
        self.assertEqual([record.address for record in records], [0, 0, 0])

    def test_one_based_discrete_offsets_are_normalized(self) -> None:
        stream = StringIO(
            "data_type;address;label;value\n"
            "Discrete Inputs;1;First input;0\n"
            "Discrete Inputs;2;Second input;1\n"
        )

        records, skipped = parse_csv(stream, "Discrete Inputs")

        self.assertEqual(skipped, 0)
        self.assertEqual([record.address for record in records], [0, 1])
        self.assertEqual(
            [format_reference_address(record.data_type, record.address) for record in records],
            ["10001", "10002"],
        )

    def test_zero_based_discrete_offsets_are_preserved(self) -> None:
        stream = StringIO(
            "data_type,address,value\n"
            "Discrete Inputs,0,0\n"
            "Discrete Inputs,1,1\n"
        )

        records, skipped = parse_csv(stream, "Discrete Inputs")

        self.assertEqual(skipped, 0)
        self.assertEqual([record.address for record in records], [0, 1])

    def test_holding_register_range_is_imported(self) -> None:
        stream = StringIO(
            "data_type,address,label,value,range\n"
            'Holding Registers,40001,Temperature,12,"10;100"\n'
        )

        records, skipped = parse_csv(stream, "Holding Registers")

        self.assertEqual(skipped, 0)
        self.assertEqual(records[0].value_range, (10, 100))

    def test_range_in_semicolon_csv_is_imported(self) -> None:
        stream = StringIO(
            "data_type;address;label;value;range\n"
            'Holding Registers;40001;Temperature;12;"10;100"\n'
        )

        records, skipped = parse_csv(stream, "Holding Registers")

        self.assertEqual(skipped, 0)
        self.assertEqual(records[0].value_range, (10, 100))


class RandomValueTests(unittest.TestCase):
    def test_parse_and_format_register_range(self) -> None:
        self.assertEqual(parse_register_range(" 10 ; 100 "), (10, 100))
        self.assertEqual(parse_register_range("08;09"), (8, 9))
        self.assertEqual(format_register_range((10, 100)), "10;100")

    def test_invalid_register_ranges_are_rejected(self) -> None:
        for value in ("10", "10;", "20;10", "-1;10", "0;65536", "a;b"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_register_range(value)

    def test_random_value_uses_inclusive_range(self) -> None:
        calls: list[tuple[int, int]] = []

        def fake_randint(minimum: int, maximum: int) -> int:
            calls.append((minimum, maximum))
            return maximum

        self.assertEqual(random_register_value((5, 9), fake_randint), 9)
        self.assertEqual(calls, [(5, 9)])


class ExtendedRandomTests(unittest.TestCase):
    def test_input_register_range_csv(self) -> None:
        records, skipped = parse_csv(StringIO(
            'data_type,address,value,range\nInput Registers,30001,12,10;100\n'
        ), "Input Registers")
        self.assertEqual(skipped, 0)
        self.assertEqual(records[0].value_range, (10, 100))
        self.assertEqual(records[0].address, 0)

    def test_random_cycle_updates_inputs_and_respects_type_toggles(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from modbus_app.gui import ModbusSlaveApp

        model = DataModel(4)
        model.set("Holding Registers", 0, [77])
        app = SimpleNamespace(
            model=model,
            random_enabled={
                name: Mock(get=Mock(return_value=enabled))
                for name, enabled in (("Holding Registers", False),
                                      ("Input Registers", True), ("Discrete Inputs", True))
            },
            register_ranges={("Holding Registers", 0): (1, 1),
                             ("Input Registers", 0): (42, 42),
                             ("Input Registers", 9): (99, 99)},
            saved_values={}, tables=[], after=Mock(return_value="timer"),
            _run_random_cycle=Mock(),
        )
        with patch("modbus_app.gui.random_register_value", side_effect=[42, 0, 1, 0, 1]):
            ModbusSlaveApp._run_random_cycle(app)
        self.assertEqual(model.get("Input Registers", 0), [42])
        self.assertEqual(model.get("Discrete Inputs", 0, 4), [False, True, False, True])
        self.assertEqual(model.get("Holding Registers", 0), [77])
        self.assertEqual(app.saved_values[("Discrete Inputs", 3)], 1)
        app.after.assert_called_once_with(5000, app._run_random_cycle)
        for variable in app.random_enabled.values():
            variable.get.return_value = False
        app.after.reset_mock()
        ModbusSlaveApp._run_random_cycle(app)
        app.after.assert_not_called()


class TcpServerTests(unittest.TestCase):
    def test_tcp_write_then_read(self) -> None:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]

        running = threading.Event()
        stopped = threading.Event()
        errors: list[str] = []

        def on_status(_message: str, kind: str) -> None:
            if kind == "running":
                running.set()
            elif kind == "stopped":
                stopped.set()

        runner = ModbusServerRunner(on_status, errors.append)
        runner.start(AppConfig(tcp_host="127.0.0.1", tcp_port=port, data_size=10))
        self.assertTrue(running.wait(3), "TCP server did not start")

        client = ModbusTcpClient("127.0.0.1", port=port)
        try:
            for _ in range(30):
                if client.connect():
                    break
                time.sleep(0.05)
            else:
                self.fail("TCP client could not connect")

            write_result = client.write_register(0, 4321, device_id=1)
            self.assertFalse(write_result.isError(), str(write_result))
            read_result = client.read_holding_registers(0, count=1, device_id=1)
            self.assertFalse(read_result.isError(), str(read_result))
            self.assertEqual(read_result.registers, [4321])
        finally:
            client.close()
            runner.stop()
            stopped.wait(3)

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
