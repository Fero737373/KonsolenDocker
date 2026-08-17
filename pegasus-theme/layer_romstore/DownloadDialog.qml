// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick 2.6


FocusScope {
    id: root

    property string jobState: ""
    property string message: ""
    property real progress: 0
    property string progressText: ""
    property bool active: false

    visible: jobState !== ""
    focus: visible
    z: 100

    Rectangle {
        anchors.fill: parent
        color: "#000"
        opacity: 0.75
    }

    Rectangle {
        anchors.centerIn: parent
        width: parent.width * 0.58
        height: vpx(245)
        radius: vpx(4)
        color: "#111"
        border { color: "#222"; width: vpx(2) }

        Column {
            anchors.fill: parent
            anchors.margins: vpx(28)
            spacing: vpx(17)

            Text {
                text: root.jobState === "completed" ? "Download abgeschlossen"
                      : root.jobState === "failed" ? "Download fehlgeschlagen"
                      : root.jobState === "cancelled" ? "Download abgebrochen"
                      : "ROM wird geladen"
                color: "#eee"
                font {
                    family: globalFonts.sans
                    bold: true
                    capitalization: Font.SmallCaps
                    pixelSize: vpx(30)
                }
            }
            Text {
                text: root.message
                width: parent.width
                color: "#eee"
                font { family: globalFonts.sans; pixelSize: vpx(16) }
                wrapMode: Text.WordWrap
            }
            Rectangle {
                width: parent.width
                height: vpx(18)
                radius: vpx(3)
                color: "#222"
                visible: root.active

                Rectangle {
                    width: parent.width * Math.max(0.02, root.progress)
                    height: parent.height
                    radius: vpx(3)
                    color: "#4ae"
                }
            }
            Text {
                text: root.progressText
                color: "#aaa"
                font { family: globalFonts.sans; pixelSize: vpx(14) }
            }
            Rectangle {
                width: parent.width
                height: modalLabel.height * 1.75
                radius: vpx(3)
                color: "#4ae"
                border.width: vpx(1)

                Text {
                    id: modalLabel
                    anchors.centerIn: parent
                    text: root.active ? "B drücken zum Abbrechen" : "B drücken zum Schließen"
                    color: "#eee"
                    font { family: globalFonts.sans; bold: true; pixelSize: vpx(18) }
                }
            }
        }
    }
}
