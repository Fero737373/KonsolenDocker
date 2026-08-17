// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick 2.6


Rectangle {
    id: root

    property var selectedItem: null
    property string collectionName: ""
    property string statusMessage: ""
    property string warningMessage: ""
    property string downloadSizeText: ""

    color: "#111"

    Rectangle {
        color: "#222"
        width: vpx(2)
        anchors { top: parent.top; bottom: parent.bottom; left: parent.right }
    }

    Column {
        anchors {
            left: parent.left; leftMargin: vpx(30)
            right: parent.right; rightMargin: vpx(30)
            top: parent.top; topMargin: vpx(34)
        }
        spacing: vpx(14)

        Text {
            width: parent.width
            text: "Downloads"
            color: "#4ae"
            font {
                pixelSize: vpx(17)
                family: globalFonts.sans
                capitalization: Font.AllUppercase
            }
        }
        Text {
            width: parent.width
            text: root.selectedItem ? root.selectedItem.title : root.collectionName
            color: "#eee"
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            font {
                bold: true
                pixelSize: vpx(30)
                capitalization: Font.SmallCaps
                family: globalFonts.sans
            }
        }
        Text {
            width: parent.width
            text: root.selectedItem
                  ? root.selectedItem.kind + " — " + root.selectedItem.sourceName
                  : root.statusMessage
            color: "#eee"
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            font { pixelSize: vpx(18); family: globalFonts.sans }
        }
        Text {
            width: parent.width
            text: root.selectedItem && root.selectedItem.developerName
                  ? root.selectedItem.developerName : ""
            color: "#4ae"
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            font { pixelSize: vpx(16); family: globalFonts.sans }
        }
        Text {
            width: parent.width
            text: root.selectedItem ? root.selectedItem.descriptionText : ""
            color: "#eee"
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignJustify
            maximumLineCount: 9
            elide: Text.ElideRight
            font { pixelSize: vpx(16); family: globalFonts.sans }
        }
        Text {
            width: parent.width
            text: root.selectedItem && root.selectedItem.licenseName
                  ? "Lizenz: " + root.selectedItem.licenseName : ""
            color: "#aaa"
            wrapMode: Text.WordWrap
            font { pixelSize: vpx(14); family: globalFonts.sans }
        }
        Text {
            width: parent.width
            text: root.downloadSizeText ? "Download: " + root.downloadSizeText : ""
            color: "#aaa"
            font { pixelSize: vpx(14); family: globalFonts.sans }
        }
        Text {
            width: parent.width
            text: root.warningMessage
            color: "#faa"
            wrapMode: Text.WordWrap
            maximumLineCount: 2
            elide: Text.ElideRight
            font { pixelSize: vpx(13); family: globalFonts.sans }
        }
    }

    Rectangle {
        anchors {
            left: parent.left; right: parent.right
            leftMargin: vpx(30); rightMargin: vpx(30)
            bottom: helpText.top; bottomMargin: vpx(12)
        }
        height: buttonLabel.height * 2.5
        radius: vpx(3)
        color: root.selectedItem && !root.selectedItem.installed ? "#4ae" : "#aaa"
        border.width: vpx(1)

        Text {
            id: buttonLabel
            anchors.centerIn: parent
            text: root.selectedItem && root.selectedItem.installed ? "Installiert" : "Download"
            color: root.selectedItem && !root.selectedItem.installed ? "#eee" : "#666"
            font { pixelSize: vpx(18); family: globalFonts.sans; bold: true }
        }
    }

    Text {
        id: helpText
        anchors {
            left: parent.left; right: parent.right
            bottom: parent.bottom; margins: vpx(16)
        }
        text: "A Auswählen     X Aktualisieren     B Zurück"
        color: "#eee"
        horizontalAlignment: Text.AlignHCenter
        font { pixelSize: vpx(15); family: globalFonts.sans; bold: true }
    }
}
