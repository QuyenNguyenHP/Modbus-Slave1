from __future__ import annotations

import socket
import threading
import time
import unittest

from pymodbus.client import ModbusTcpClient

from modbus_app.config import AppConfig
from modbus_app.server import DataModel, ModbusServerRunner


class DataModelTests(unittest.TestCase):
    def test_register_and_bit_values(self) -> None:
        model = DataModel(10)
        model.set("Holding Registers", 0, [1234, 0xFFFF])
        model.set("Coils", 9, [1])
        self.assertEqual(model.get("Holding Registers", 0, 2), [1234, 0xFFFF])
        self.assertEqual(model.get("Coils", 9), [True])


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
