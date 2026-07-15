# Modbus Slave Simulator

A configurable desktop Modbus Slave/Server simulator supporting **Modbus TCP** and **Modbus RTU**.

## Features

- Select TCP or RTU mode from the user interface.
- Configure Slave ID, bind address/TCP port, COM port, baud rate, data bits, parity, stop bits, and timeout.
- Display two data tables simultaneously, defaulting to Discrete Inputs and Holding Registers.
- Select Coils, Discrete Inputs, Holding Registers, or Input Registers independently for each table.
- Display Address, Label, and Value; double-click a label or value to edit it.
- Show Coils and Discrete Inputs as status dots; click a dot to toggle gray (`0`) and green (`1`).
- Use `dq logo.jpeg` as the application window and taskbar icon.
- Import and export each table as CSV.
- Automatically detect COM ports, save the most recent settings, and import/export JSON settings.
- Show server status and activity logs in real time.

## Requirements

- Windows 10/11.
- Python 3.10 or later. Select **Add Python to PATH** when installing Python from python.org.

## Quick start

Double-click `run.bat`. On the first run, it creates `.venv` and installs the required dependencies automatically.

To run manually:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

## Usage

1. Select `TCP` or `RTU` and enter the connection settings.
2. Set the number of addresses to simulate. The default is 100, representing addresses 0 through 99.
3. Click **Start**.
4. Select the data types to display. Double-click labels or values to edit them.
5. Connect from a Modbus Master using the configured Slave ID and connection settings.

## CSV format

Each table has **Import CSV** and **Export CSV** buttons. Exported files use UTF-8 and this structure:

```csv
data_type,address,label,value
Discrete Inputs,10001,Run feedback,1
Discrete Inputs,10002,Alarm,0
Holding Registers,40001,Speed setpoint,1500
```

The `address` and `value` columns are required when importing. If `data_type` is omitted, rows are imported into the data type currently selected in that table. The `label` column is optional.

Imports accept comma-, semicolon-, or tab-separated files. Legacy Modbus references are converted automatically: `10001` for Discrete Inputs, `30001` for Input Registers, and `40001` for Holding Registers all map to zero-based address `0`. When the server is stopped, importing a larger address range automatically increases **Data size**.

For Coils and Discrete Inputs, files whose address list starts at `1` and contains no address `0` are treated as one-based offsets. For example, Discrete Input `1` is displayed as standard reference `10001`. Files containing address `0` remain zero-based.

The default TCP port is `5020`, which normally does not require Administrator privileges. Using the standard port `502` may require elevated privileges or a Windows Firewall rule. For RTU, the selected COM port must not be in use by another application.

## Data mapping

| Data type | Read functions | Write functions |
|---|---:|---:|
| Coils | 01 | 05, 15 |
| Discrete Inputs | 02 | Editable from the UI only |
| Holding Registers | 03 | 06, 16 |
| Input Registers | 04 | Editable from the UI only |

Displayed and exported addresses use standard Modbus references: `00001` for Coils, `10001` for Discrete Inputs, `30001` for Input Registers, and `40001` for Holding Registers. These first rows correspond to zero-based address `0` in a Master request. The **Start** field remains a zero-based offset.
