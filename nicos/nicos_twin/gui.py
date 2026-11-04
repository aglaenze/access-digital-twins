"""Main window of the ESS NICOS GUI ("flowui"), with a workaround for a NICOS bug at the tested commit (44bec9c).

The generic main window (nicos/clients/gui/mainwindow.py) uses an action `actionInstrumentWebsite` that the flowui
window (nicos/clients/flowui/mainwindow.py, used by all ESS instruments) does not define: the GUI crashes when it
starts. Here the missing action is added; nothing else changes. To be removed once fixed upstream.
"""
from nicos.clients.flowui.mainwindow import MainWindow as FlowuiMainWindow
from nicos.guisupport.qt import QAction


class MainWindow(FlowuiMainWindow):
    def _ensure_website_action(self):
        if not hasattr(self, "actionInstrumentWebsite"):
            self.actionInstrumentWebsite = QAction("Instrument &home page", self)
            self.actionInstrumentWebsite.setVisible(False)

    def on_client_connected(self):
        self._ensure_website_action()
        FlowuiMainWindow.on_client_connected(self)

    def on_client_disconnected(self):
        self._ensure_website_action()
        FlowuiMainWindow.on_client_disconnected(self)
