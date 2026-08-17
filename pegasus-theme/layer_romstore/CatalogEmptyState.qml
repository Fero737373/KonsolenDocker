// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick 2.6


Column {
    id: root

    property string loadState: "idle"
    property string statusMessage: ""
    property string warningMessage: ""

    spacing: vpx(16)

    Image {
        anchors.horizontalCenter: parent.horizontalCenter
        visible: root.loadState === "loading"
        source: "../assets/loading-spinner.png"
        RotationAnimator on rotation {
            loops: Animator.Infinite
            from: 0; to: 360; duration: 500
        }
    }
    Text {
        width: parent.width
        text: root.loadState === "loading" ? "Katalog wird geladen …" : root.statusMessage
        color: "#eee"
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        font { bold: true; pixelSize: vpx(24); family: globalFonts.sans }
    }
    Text {
        width: parent.width
        text: root.loadState === "error" ? "A drücken, um erneut zu versuchen." : root.warningMessage
        color: "#4ae"
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        font { pixelSize: vpx(16); family: globalFonts.sans }
    }
}
