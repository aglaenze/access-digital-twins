"""NICOS GUI configuration of the ODIN digital twin (standard NICOS panels only)."""

main_window = docked(
    tabbed(
        ('Command line',
         vsplit(
             panel('nicos.clients.gui.panels.cmdbuilder.CommandPanel'),
             panel('nicos.clients.gui.panels.status.ScriptStatusPanel', eta=True),
             panel('nicos.clients.gui.panels.console.ConsolePanel', hasinput=False),
         ),
        ),
        ('Detector image',
         panel('nicos.clients.gui.panels.live.LiveDataPanel'),
        ),
    ),
    ('ODIN devices',
     panel('nicos.clients.gui.panels.devices.DevicesPanel',
           dockpos='right',
           param_display={'Exp': ['lastpoint', 'lastscan'], 'det': ['lastfile']},
           filters=[('Detector', 'det'), ('Sample stage', '^stage'), ('Beam', 'chopper|pinhole|diffuser|shutter|wfm')],
     ),
    ),
    ('Experiment',
     panel('nicos.clients.gui.panels.expinfo.ExpInfoPanel', dockpos='right'),
    ),
)

windows = [
    window('Editor', 'editor',
           vsplit(
               panel('nicos.clients.gui.panels.scriptbuilder.CommandsPanel'),
               panel('nicos.clients.gui.panels.editor.EditorPanel'),
           )),
    window('Scans', 'plotter', panel('nicos.clients.gui.panels.scans.ScansPanel')),
    window('History', 'find', panel('nicos.clients.gui.panels.history.HistoryPanel')),
    window('Live data', 'live', panel('nicos.clients.gui.panels.live.LiveDataPanel')),
    window('Log files', 'table', panel('nicos.clients.gui.panels.logviewer.LogViewerPanel')),
    window('Errors', 'errors', panel('nicos.clients.gui.panels.errors.ErrorPanel')),
]

tools = [
    tool('Calculator', 'nicos.clients.gui.tools.calculator.CalculatorTool'),
]

options = {}
