import QtQuick
import QtQuick.Layouts
import Quickshell.Io
import qs.Commons
import qs.Ui

BarWidget {
  id: root
  moduleName: "local.cpu-mode"

  property string mode: "unknown"
  readonly property bool quiet: mode === "quiet"
  property bool popupOpen: false
  property bool popupPinned: false
  property var metrics: null
  property string metricsOutput: ""
  property string metricsError: ""
  property string sensorWarnings: ""
  property string statusOutput: ""
  property string statusError: ""
  property string actionError: ""
  readonly property string warning: actionError || statusError || metricsError
    || (sensorWarnings ? "Some sensors could not be read (see shell log)." : "")
  readonly property var metricRows: {
    var data = metrics || {}
    var rows = [
      { label: "CPU temperature", value: metricText(data.temperature_c, " °C", 1) },
      { label: "CPU usage", value: metricText(data.usage_percent, "%", 1) },
      { label: "CPU clock (average)", value: metricText(data.frequency_mhz / 1000, " GHz", 2, data.frequency_mhz) }
    ]
    if (metrics && data.fans.length > 0) {
      for (var i = 0; i < data.fans.length; i++)
        rows.push({ label: data.fans[i].label,
          value: data.fans[i].rpm === null ? "Unavailable" : data.fans[i].rpm + " RPM" })
    } else {
      rows.push({ label: "Fan speed", value: metrics ? "Not exposed" : metricText(null, "", 0) })
    }
    rows.push({ label: "Turbo Boost", value: !metrics ? metricText(null, "", 0)
      : data.turbo_enabled === null ? "Unavailable" : data.turbo_enabled ? "Enabled" : "Disabled" })
    rows.push({ label: "Performance cap", value: metricText(data.performance_limit_percent, "%", 0) })
    return rows
  }

  function metricText(value, unit, decimals, source) {
    if (!metrics) return metricsError ? "Unavailable" : "Loading..."
    if (value === null || value === undefined || source === null || !isFinite(value)) return "Unavailable"
    return Number(value).toFixed(decimals) + unit
  }

  function refresh() {
    if (!statusProc.running) statusProc.running = true
  }

  function refreshMetrics() {
    if (popupOpen && !metricsProc.running) {
      metricsOutput = ""
      metricsProc.running = true
    }
  }

  function close() {
    hoverOpen.stop()
    hoverClose.stop()
    popupPinned = false
    popupOpen = false
  }

  function updateHover() {
    if (popupPinned) return
    if (button.tooltipHovered || popup.containsMouse) {
      hoverClose.stop()
      if (!popupOpen) hoverOpen.restart()
    } else {
      hoverOpen.stop()
      if (popupOpen) hoverClose.restart()
    }
  }

  function pinPopup() {
    hoverOpen.stop()
    hoverClose.stop()
    popupPinned = true
    popupOpen = true
  }

  function acceptMetrics() {
    var data
    try {
      data = JSON.parse(metricsOutput)
    } catch (error) {
      metrics = null
      metricsError = "Invalid CPU metrics (see shell log)."
      console.warn("CPU Mode: invalid metrics output:", error)
      return
    }
    if (!data || !Array.isArray(data.fans) || !Array.isArray(data.errors)) {
      metrics = null
      metricsError = "Invalid CPU metrics (see shell log)."
      console.warn("CPU Mode: invalid metrics structure")
      return
    }
    metrics = data
    metricsError = ""
    var warnings = data.errors.join("\n")
    if (warnings && warnings !== sensorWarnings) console.warn("CPU Mode sensors:", warnings)
    sensorWarnings = warnings
  }

  onPopupOpenChanged: {
    if (popupOpen) {
      metrics = null
      metricsError = ""
      refresh()
      refreshMetrics()
    }
  }
  Component.onCompleted: refresh()

  Process {
    id: statusProc
    command: ["/usr/local/bin/omarchy-cpu-mode", "status"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.statusOutput = text.trim()
    }
    stderr: StdioCollector { id: statusStderr; waitForEnd: true }
    onExited: function(exitCode) {
      if (exitCode === 0 && (root.statusOutput === "quiet" || root.statusOutput === "full")) {
        root.mode = root.statusOutput
        root.statusError = ""
      } else {
        root.mode = "unknown"
        root.statusError = "CPU mode unavailable (see shell log)."
        console.warn("CPU Mode status failed:", statusStderr.text || root.statusOutput)
      }
    }
  }

  Process {
    id: toggleProc
    command: ["pkexec", "/usr/local/bin/omarchy-cpu-mode", "toggle"]
    stderr: StdioCollector { id: toggleStderr; waitForEnd: true }
    onExited: function(exitCode) {
      if (exitCode !== 0) {
        root.actionError = "Could not switch CPU mode (see shell log)."
        console.warn("CPU Mode toggle failed:", toggleStderr.text)
        root.pinPopup()
      } else {
        root.actionError = ""
      }
      root.refresh()
      root.refreshMetrics()
    }
  }

  Process {
    id: metricsProc
    command: ["python3", decodeURIComponent(Qt.resolvedUrl("cpu-metrics.py").toString().replace(/^file:\/\//, ""))]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.metricsOutput = text
    }
    stderr: StdioCollector { id: metricsStderr; waitForEnd: true }
    onExited: function(exitCode) {
      if (exitCode === 0) root.acceptMetrics()
      else {
        root.metrics = null
        root.metricsError = "CPU metrics unavailable (see shell log)."
        console.warn("CPU Mode metrics failed:", metricsStderr.text)
      }
    }
  }

  Timer {
    interval: 5000
    running: true
    repeat: true
    onTriggered: root.refresh()
  }

  Timer {
    interval: 2000
    running: root.popupOpen
    repeat: true
    onTriggered: root.refreshMetrics()
  }

  Timer {
    id: hoverOpen
    interval: 400
    onTriggered: if (button.tooltipHovered && root.bar && (!root.bar.activePopout || root.bar.activePopout === root))
      root.popupOpen = true
  }

  Timer {
    id: hoverClose
    interval: 300
    onTriggered: if (!root.popupPinned && !button.tooltipHovered && !popup.containsMouse) root.close()
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.quiet ? "Q" : root.mode === "full" ? "F" : "?"
    tooltipText: ""
    onTooltipHoveredChanged: root.updateHover()

    onPressed: function(b) {
      if (b === Qt.RightButton) {
        if (root.popupPinned) root.close()
        else root.pinPopup()
      } else if (b === Qt.LeftButton && !toggleProc.running) {
        root.actionError = ""
        toggleProc.running = true
      }
    }
  }

  PopupCard {
    id: popup
    anchorItem: button
    bar: root.bar
    owner: root
    open: root.popupOpen
    triggerMode: root.popupPinned ? "click" : "hover"
    contentWidth: fittedContentWidth(Style.space(320))
    contentHeight: fittedContentHeight(column.implicitHeight)
    onContainsMouseChanged: root.updateHover()

    Column {
      id: column
      width: parent.width
      spacing: Style.space(10)

      Text {
        width: parent.width
        textFormat: Text.PlainText
        text: "CPU  /  " + (toggleProc.running ? "Switching..." : root.quiet ? "Quiet"
          : root.mode === "full" ? "Full speed" : "Unknown mode")
        color: Color.popups.text
        font.family: Style.font.family
        font.pixelSize: Style.font.subtitle
        font.bold: true
      }

      PanelSeparator { width: parent.width; foreground: Color.popups.text }

      Repeater {
        model: root.metricRows

        RowLayout {
          required property var modelData
          width: column.width
          spacing: Style.space(12)

          Text {
            Layout.fillWidth: true
            textFormat: Text.PlainText
            text: modelData.label
            elide: Text.ElideRight
            color: Color.popups.text
            font.family: Style.font.family
            font.pixelSize: Style.font.bodySmall
          }

          Text {
            textFormat: Text.PlainText
            text: modelData.value
            color: Color.popups.text
            font.family: Style.font.family
            font.pixelSize: Style.font.bodySmall
          }
        }
      }

      Text {
        width: parent.width
        visible: root.warning !== ""
        textFormat: Text.PlainText
        text: root.warning
        wrapMode: Text.WordWrap
        color: Color.urgent
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
      }

      PanelSeparator { width: parent.width; foreground: Color.popups.text }

      Text {
        width: parent.width
        textFormat: Text.PlainText
        text: root.popupPinned
          ? "Left-click Q/F to toggle.\nRight-click again or click outside to close."
          : "Left-click Q/F to toggle. Right-click to pin."
        wrapMode: Text.WordWrap
        color: Color.popups.text
        opacity: 0.7
        font.family: Style.font.family
        font.pixelSize: Style.font.caption
      }
    }
  }
}
