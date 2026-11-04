"""NICOS GUI of the ODIN digital twin: copy of nicos_ess/odin/guiconfig.py (the GUI of the real ODIN)."""

main_window = docked(
    tabbed(
        ('Experiment', panel('nicos_twin.gui.ExpPanel')),
        ('Setup',
         panel('nicos.clients.flowui.panels.setup_panel.SetupsPanel')),
        ('  ', panel('nicos.clients.flowui.panels.empty.EmptyPanel')),
        (
            'Instrument interaction',
            hsplit(
                vbox(
                    panel(
                        'nicos.clients.flowui.panels.cmdbuilder.CommandPanel',
                    ),
                    tabbed(
                        ('Output',
                         panel(
                             'nicos.clients.flowui.panels.console.ConsolePanel',
                             hasinput=False)),
                        ('Scan Plot',
                         panel('nicos.clients.flowui.panels.scans.ScansPanel')
                         ),
                        ('Detector Image',
                         panel(
                             'nicos_ess.odin.gui.panels.live.MultiLiveDataPanel'
                         )),
                        ('Script Status',
                         panel(
                             'nicos.clients.flowui.panels.status.ScriptStatusPanel',
                             eta=True)),
                    ),
                ),  # vsplit
                panel(
                    'nicos.clients.flowui.panels.devices.DevicesPanel',
                    dockpos='right',
                    param_display={'Exp': ['lastpoint', 'lastscan']},
                    filters=[],
                ),
            ),  # hsplit
        ),
        (
            'Scripting',
            panel('nicos.clients.flowui.panels.editor.EditorPanel',
                  tools=None),
        ),
        (
            'History',
            panel('nicos.clients.flowui.panels.history.HistoryPanel'),
        ),
        (
            'Logs',
            tabbed(
                ('Errors',
                 panel('nicos.clients.gui.panels.errors.ErrorPanel')),
                ('Log files',
                 panel('nicos.clients.gui.panels.logviewer.LogViewerPanel')),
            ),
        ),
        position='left',
        margins=(0, 0, 0, 0),
        textpadding=(30, 20),
    ),  # tabbed
)  # docked

windows = []

tools = [
    tool('Report NICOS bug or request enhancement',
         'nicos.clients.gui.tools.bugreport.BugreportTool'),
]

options = {
    # ESS flowui window, with a workaround for a NICOS bug (see nicos_twin/gui.py)
    'mainwindow_class': 'nicos_twin.gui.MainWindow',
}
