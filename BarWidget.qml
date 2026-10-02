import QtQuick
import Quickshell.Io
import qs.Ui

BarWidget {
  id: root
  moduleName: "local.cpu-mode"

  property string mode: "unknown"
  readonly property bool quiet: mode === "quiet"

  function refresh() {
    if (!statusProc.running) statusProc.running = true
  }

  Component.onCompleted: refresh()

  Process {
    id: statusProc
    command: ["/usr/local/bin/omarchy-cpu-mode", "status"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.mode = text.trim()
    }
  }

  Process {
    id: toggleProc
    command: ["pkexec", "/usr/local/bin/omarchy-cpu-mode", "toggle"]
    onExited: root.refresh()
  }

  Timer {
    interval: 5000
    running: true
    repeat: true
    onTriggered: root.refresh()
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.quiet ? "Q" : "F"
    tooltipText: root.quiet
      ? "CPU Quiet · click for Full Speed"
      : "CPU Full Speed · click for Quiet"

    onPressed: function(b) {
      if (b === Qt.LeftButton && !toggleProc.running)
        toggleProc.running = true
    }
  }
}
