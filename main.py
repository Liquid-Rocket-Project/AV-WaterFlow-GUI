"""
RUN THIS PROGRAM FOR THE GUI

Author: Nick Fan
Date: 3/4/2023
Description: Quick GUI to aid in waterflow testing and gain more precise timing.
Written in one day so please do not judge quality of code LOL.
"""

import os
import pandas as pd
import serial
import serial.tools.list_ports
import sys
import time

from collections import defaultdict
from PyQt6 import QtSerialPort
from PyQt6.QtCore import Qt, QTimer, QDateTime
from PyQt6.QtGui import QIcon

from PyQt6.QtWidgets import (
    QApplication,
    QGridLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QComboBox,
    QWidget,
    QLineEdit,
    QTextEdit,
    QSpacerItem,
    QMessageBox,
    QInputDialog
)

# CONSTANTS -------------------------------------------------------------------|
MIN_SIZE = 500
LINE_HEIGHT = 35
SETTING_WIDTH = 150
BOX_SIZE = 300
DATE_TIME_FORMAT = "MM/dd/yyyy | hh:mm:ss -> "
WINDOW_ICON_P = "./src/hydraLogo.png"
ERROR_ICON_P = "./src/errorIcon.png"
WARNING_ICON_P = "./src/warningIcon.png"
BAUDRATE = 9600
WARNING = 0
ERROR = 1
MESSAGE_LABELS = ("Warning", "Error")
DATE = QDateTime.currentDateTime().toString("MM-dd-yy")
USB_NAME = "USB-SERIAL CH340"

# HELPER CLASS -----------------------------------------------------------------|
class SerialComm():
    """Serial Com Manager."""

    def __init__(self, com: str, baudrate: int):
        self.port = com
        self.baudrate = baudrate
        self.connection = serial.Serial(self.port, self.baudrate, timeout=0.05)
    
    def receiveMessage(self):
        """Read from serial com if there is data in."""
        try:
            data = str(self.connection.readall().decode("ascii"))
            if data:
                return data
        except serial.SerialException:
            return False

    def sendMessage(self, message: str) -> bool:
        """Write to serial com."""
        if not self.connection.is_open:
            self.connection.open()
        try:
            self.connection.write(message.encode("utf-8"))
            time.sleep(.002)
            return True
        except serial.SerialException:
            return False
    
    def setPort(self, newPort: str) -> bool:
        """Set new com port"""
        # this doesn't really work as intended, on a windows device currently
        if os.path.exists(f"/dev/{self.connection.name}"):
            self.connection = serial.Serial(newPort, self.baudrate)
            if not self.connection.is_open:
                self.connection.open()
            return True
        return False
    
    def setBaudrate(self, newBaudrate: int) -> None:
        """Set new baudrate"""
        self.baudrate = newBaudrate
    
    def close(self):
        """Close connection."""
        self.connection.close()

    @staticmethod
    def getPorts():
        """Returns list of ports and port descriptions."""
        ports = serial.tools.list_ports.comports()
        return [(desc, port) for port, desc, hwid in ports]


# MAIN GUI ---------------------------------------------------------------------|
class WaterFlowGUI(QMainWindow):
    """Simple Waterflow Assistant GUI."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("WaterFlow Control")
        self.setWindowIcon(QIcon(WINDOW_ICON_P))
        self.setMinimumSize(MIN_SIZE * 2, MIN_SIZE)
        self.generalLayout = QGridLayout()
        centralWidget = QWidget()
        centralWidget.setLayout(self.generalLayout)
        self.setCentralWidget(centralWidget)

        self.ports = [info for info in QtSerialPort.QSerialPortInfo.availablePorts()]
        self.serialCon = SerialComm(self.ports[0].portName(), BAUDRATE)

        self.presetCounter = QTimer()
        self.presetCounter.timeout.connect(self._presetSendReceive)
        self.inPreset = False

        self._createInputLine()
        self._createDisplayArea()
        self._createSettingsBox()

        self._logSystem(
            "NEW SESSION: " 
            + QDateTime.currentDateTime().toString("hh:mm:ss")
        )

    @staticmethod
    def createMessageBox(boxType: int, message: str) -> None:
        """Creates error message popup with indicated message."""
        box = QMessageBox()
        if boxType == ERROR:
            box.setWindowIcon(QIcon(ERROR_ICON_P))
        else:
            box.setWindowIcon(QIcon(WARNING_ICON_P))
        box.setWindowTitle(MESSAGE_LABELS[boxType])
        box.setText(f"{MESSAGE_LABELS[boxType]}: {message}")
        box.exec()
    
    def checkPortsOk(self) -> bool:
        """Checks for serial connection."""
        if self.ports[0].description() != USB_NAME:
            self.createMessageBox(ERROR, "No USB Serial detected.\nPlease check your connection first.")
            self.close()
            return False
        return True

    def closeEvent(self, event) -> None:
        """Adds additional functions when closing window."""
        self._logSystem("-------------------")
        if self.serialCon:
            self.serialCon.close()
    
    def _logSystem(self, entry: str) -> None:
        """Log serial monitor activity to text file."""
        with open(f"./log/system/system{DATE}.txt", "a") as sysLog:
            sysLog.write(entry + "\n")

    def _sendSerial(self, input: str) -> None:
        """Writes to serial port."""
        message = QDateTime.currentDateTime().toString(DATE_TIME_FORMAT)
        message += input
        repeat = False
        if len(set(input)) != len(input):
            message += " -- Repeat detected, try again"
            repeat = True
        self.line.clear()
        self.monitor.append(message)
        self._logSystem(message)
        if not repeat: 
            if not self.serialCon.sendMessage(input):
                self.createMessageBox(ERROR, "COM unavailable for sending.")

    def _readSerial(self) -> None:
        """Reads from serial port."""
        response = self.serialCon.receiveMessage()
        if response:
            response = response.strip("\n").split("\n")
        else:
            response = ("No response",)
        for line in response:
            self.monitor.append(
                QDateTime.currentDateTime().toString(DATE_TIME_FORMAT) 
                + line
            )

    def _sendReceiveOnEnter(self) -> None:
        """Signal for input line receiver enter."""
        self._sendSerial(self.line.text())
        self._readSerial()

    def _createInputLine(self) -> None:
        """Create input line for sending commands."""
        self.line = QLineEdit()
        self.line.setFixedHeight(LINE_HEIGHT)
        self.line.returnPressed.connect(self._sendReceiveOnEnter)
        self.generalLayout.addWidget(self.line)

    def _createDisplayArea(self) -> None:
        """Create text display area."""
        self.monitor = QTextEdit()
        self.monitor.setReadOnly(True)
        self.generalLayout.addWidget(self.monitor)
    
    def _exitPreset(self) -> None:
        """Exit preset run."""
        self.inPreset = False
        self._logPreset()
        self.timeInterval.setReadOnly(False)
        self.toggledPins.setReadOnly(False)
        self.testName.setReadOnly(False)
        self.measurementUnits.setReadOnly(False)

    def _presetSendReceive(self) -> None:
        """Helper function for preset run."""
        self._sendSerial(self.toggledPins.text())
        self._readSerial()
        self.presetCounter.stop()
        if self.inPreset:
            self._exitPreset()

    def _presetRun(self) -> None:
        """Run test with preset values."""
        try:
            presetTime = int(self.timeInterval.text())
        except ValueError:
            self.createMessageBox(ERROR, "Must set preset time as a number (seconds).")
            return

        self._presetSendReceive()
        self.inPreset = True
        self.timeInterval.setReadOnly(True)
        self.toggledPins.setReadOnly(True)
        self.testName.setReadOnly(True)
        self.measurementUnits.setReadOnly(True)
        self.presetCounter.start(1000 * presetTime)

    def _cancelPreset(self) -> None:
        """Cancels current preset run."""
        if self.inPreset:
            self.monitor.append(
                QDateTime.currentDateTime().toString(DATE_TIME_FORMAT) 
                + "Preset run aborted. Toggling pins."
            )
            self._presetSendReceive()

    def _logPreset(self) -> None:
        """Asks for data to log after a preset run."""
        dataDict = defaultdict(list)
        measurement, ok = QInputDialog().getText(
            self.centralWidget(),
            "Data Input", 
            "Please enter your data:"
        )
        if not ok:
            return
        dataDict[f"{self.testName.text()}"].append("")
        dataDict["Pins Toggled"].append(self.toggledPins.text())
        dataDict["Time Interval (s)"].append(self.timeInterval.text())
        dataDict[f"Measurement ({self.measurementUnits.text()})"].append(measurement)
        df = pd.DataFrame.from_dict(dataDict, "columns")
        df = df.transpose()
        df.to_csv(f"./log/data/data{DATE}.csv", mode='a')

    def _comPortChange(self) -> None:
        """Change COM port on combo box change."""
        changed = self.serialCon.setPort(self.comSelect.currentText())
        if not changed:
            self.createMessageBox(ERROR, "COM port is unavailable.")
            self.comSelect.setCurrentText(self.ports[0].portName())
        else:
            self.monitor.append(f"COM Port Selection: {self.serialCon.port}")

    def _createSettingsBox(self) -> None:
        """Create right side settings layout."""
        # area setup
        self.settings = QGridLayout()
        title = QLabel("Presets: ")
        topSpacer = QSpacerItem(10, 200)

        # input boxes
        self.timeInterval = QLineEdit()
        self.timeInterval.setMaximumHeight(LINE_HEIGHT)
        self.timeInterval.setMaximumWidth(SETTING_WIDTH)
        self.toggledPins = QLineEdit()
        self.toggledPins.setMaximumHeight(LINE_HEIGHT)
        self.toggledPins.setMaximumWidth(SETTING_WIDTH)
        self.measurementUnits = QLineEdit()
        self.measurementUnits.setMaximumHeight(LINE_HEIGHT)
        self.measurementUnits.setMaximumWidth(SETTING_WIDTH)
        self.testName = QLineEdit()
        self.testName.setMaximumHeight(LINE_HEIGHT)
        self.testName.setMaximumWidth(SETTING_WIDTH)

        # input buttons
        self.startPresetButton = QPushButton("Start Preset (Toggle, Wait, Toggle)")
        self.startPresetButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.startPresetButton.clicked.connect(self._presetRun)
        self.cancelPresetButton = QPushButton("Cancel Preset")
        self.cancelPresetButton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cancelPresetButton.clicked.connect(self._cancelPreset)

        # com selection combo box
        self.comSelect = QComboBox()
        self.comSelect.addItems(ports.portName() for ports in self.ports)
        self.comSelect.textActivated.connect(self._comPortChange)

        # settings layout
        self.settings.addItem(topSpacer, 0, 0)
        self.settings.addWidget(title, 1, 0)
        self.settings.addWidget(QLabel("Interval (sec): "), 2, 0)
        self.settings.addWidget(QLabel("Pins: "), 2, 1)
        self.settings.addWidget(self.timeInterval, 3, 0)
        self.settings.addWidget(self.toggledPins, 3, 1)
        self.settings.addWidget(QLabel("Test Name: "), 4, 0)
        self.settings.addWidget(QLabel("Measurement Units: "), 4, 1)
        self.settings.addWidget(self.testName, 5, 0)
        self.settings.addWidget(self.measurementUnits, 5, 1)
        self.settings.addWidget(self.startPresetButton, 6, 0)
        self.settings.addWidget(self.cancelPresetButton, 6, 1)
        self.settings.addWidget(QLabel("COM Port Select:"), 7, 0)
        self.settings.addWidget(self.comSelect, 8, 0, 2, 2)
        self.generalLayout.addLayout(self.settings, 1, 1)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    waterflowDisplay = WaterFlowGUI()
    waterflowDisplay.show()
    if not waterflowDisplay.checkPortsOk():
        sys.exit(1)
    sys.exit(app.exec())
