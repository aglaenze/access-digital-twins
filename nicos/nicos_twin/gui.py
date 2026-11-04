"""ESS NICOS GUI ("flowui"): main window and Experiment panel, with three adaptations for the twins.

1. Workaround for a NICOS bug at the tested commit (44bec9c): the generic main window
   (nicos/clients/gui/mainwindow.py) uses an action `actionInstrumentWebsite` that the flowui window
   (nicos/clients/flowui/mainwindow.py, used by all ESS instruments) does not define, so the GUI crashes when it starts.
   The missing action is added. To be removed once fixed upstream.
2. Small screens: the ESS layout needs about 1170 pixels of height (the instrument computers at ESS have large
   screens); on a laptop the bottom of the window (Apply button of the Experiment tab, device list) was out of the
   screen. The content is put in a scroll area and the window is kept within the screen.
3. Experiment panel: the Apply button right under the form (ExpPanel below), not at the bottom of the window.
"""
from nicos.clients.flowui.mainwindow import MainWindow as FlowuiMainWindow
from nicos.guisupport.qt import QAction, QApplication, QFrame, QScrollArea
from nicos_ess.gui.panels.exp_panel import ExpPanel as EssExpPanel


class ExpPanel(EssExpPanel):
    """The ESS Experiment panel, with its Apply button (and the "not applied" warning) right under the form instead
    of at the very bottom of the window (the ESS layout puts the free space between the form and the button)."""

    def __init__(self, *args, **kwargs):
        EssExpPanel.__init__(self, *args, **kwargs)
        form = self.dataBox.layout()
        for i in reversed(range(form.count())):        # the stretchable space under the form
            if form.itemAt(i).spacerItem() is not None:
                form.takeAt(i)
        outer = self.layout()
        for w in (self.applyWarningLabel, self.buttonBox):
            outer.removeWidget(w)
            form.addWidget(w)
        form.addStretch(1)                             # free space now below the button


class MainWindow(FlowuiMainWindow):
    def __init__(self, *args, **kwargs):
        FlowuiMainWindow.__init__(self, *args, **kwargs)
        content = self.takeCentralWidget()
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)
        self.setCentralWidget(scroll)
        self._fitted = False

    def showEvent(self, event):
        FlowuiMainWindow.showEvent(self, event)
        if not self._fitted:            # once: never larger than the free part of the screen
            self._fitted = True
            screen = self.screen() if hasattr(self, "screen") else QApplication.primaryScreen()
            avail = screen.availableGeometry()
            frame = self.frameGeometry().height() - self.geometry().height()
            w, h = min(self.width(), avail.width()), min(self.height(), avail.height() - frame)
            if (w, h) != (self.width(), self.height()):
                self.resize(w, h)
                self.move(avail.x() + (avail.width() - w) // 2, avail.y())

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
