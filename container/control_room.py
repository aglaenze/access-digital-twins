"""The control room of the app: a full-screen choice of the instrument, as when you walk into the control room of an
ESS instrument. Prints the chosen instrument (odin, loki) and exits; started by control_room.sh, which then opens
NICOS for that instrument. Runs with the Python of the nicos environment (PyQt5).

Test mode: CONTROL_ROOM_INSTRUMENT=odin chooses ODIN by itself after CONTROL_ROOM_DELAY seconds (default 5);
CONTROL_ROOM_SCREENSHOT=<file.png> saves a picture of the screen. CONTROL_ROOM_WINDOWED=1: a window instead of the
full screen (local app on a computer with its own desktop, control_room_local.py).
"""
import os
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

INSTRUMENTS = [("odin", "ODIN", "Imaging: radiography and tomography, wavelength by wavelength"),
               ("loki", "LoKI", "Small-angle scattering: sizes and shapes of nanostructures")]


def main():
    app = QApplication(sys.argv)
    w = QWidget()
    w.setWindowTitle("ESS control room")
    w.setStyleSheet("QWidget {background: #1D2433; color: #F2EFE6; font-family: 'DejaVu Sans';}"
                    "QPushButton {background: #2A7D6F; color: white; border-radius: 12px; padding: 22px;"
                    " font-size: 22px; text-align: left;}"
                    "QPushButton:hover {background: #33968A;}")
    lay = QVBoxLayout(w)
    windowed = bool(os.environ.get("CONTROL_ROOM_WINDOWED"))
    lay.setContentsMargins(*((40, 30, 40, 30) if windowed else (200, 120, 200, 120)))
    lay.setSpacing(24)
    title = QLabel("Which instrument?")
    title.setStyleSheet("font-size: 40px; font-weight: bold;")
    sub = QLabel("Choose the control room you walk into. NICOS, the control program of the ESS instruments, opens for "
                 "it. Close the NICOS window to come back here.")
    sub.setWordWrap(True)
    sub.setStyleSheet("font-size: 18px; color: #C9CFDA;")
    lay.addWidget(title)
    lay.addWidget(sub)
    choice = {}

    def pick(key):
        choice["instrument"] = key
        app.quit()

    for key, name, text in INSTRUMENTS:
        b = QPushButton(f"{name}\n{text}")
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda _, k=key: pick(k))
        lay.addWidget(b)
    lay.addStretch(1)
    auto = os.environ.get("CONTROL_ROOM_INSTRUMENT")
    if auto:
        QTimer.singleShot(int(float(os.environ.get("CONTROL_ROOM_DELAY", "5")) * 1000), lambda: pick(auto))
    shot = os.environ.get("CONTROL_ROOM_SCREENSHOT")             # (documentation: a picture of this screen)
    if shot:
        QTimer.singleShot(800, lambda: w.grab().save(shot))
    if windowed:
        w.resize(860, 520)
        w.show()
        w.raise_()
        w.activateWindow()
    else:
        w.showFullScreen()
    app.exec_()
    print(choice.get("instrument", ""))


if __name__ == "__main__":
    main()
