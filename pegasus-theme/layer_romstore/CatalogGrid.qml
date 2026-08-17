// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick 2.6


GridView {
    id: root

    signal downloadRequested

    property real columnCount: {
        if (cellHeightRatio > 1.2) return 5;
        if (cellHeightRatio > 0.6) return 4;
        return 3;
    }
    readonly property int maxRecalcs: 5
    property int currentRecalcs: 0
    property real cellHeightRatio: 0.5

    function updateCellHeightRatio(imageWidth, imageHeight) {
        cellHeightRatio = Math.min(Math.max(cellHeightRatio, imageHeight / imageWidth), 1.5);
    }

    function resetCells() {
        currentRecalcs = 0;
        cellHeightRatio = 0.5;
    }

    clip: true
    cellWidth: width / columnCount
    cellHeight: cellWidth * cellHeightRatio
    keyNavigationWraps: true
    displayMarginBeginning: anchors.topMargin

    Keys.onPressed: {
        if (event.isAutoRepeat)
            return;
        if (api.keys.isPageUp(event) || api.keys.isPageDown(event)) {
            event.accepted = true;
            var rowsToSkip = Math.max(1, Math.round(root.height / root.cellHeight));
            var itemsToSkip = rowsToSkip * root.columnCount;
            root.currentIndex = api.keys.isPageUp(event)
                ? Math.max(root.currentIndex - itemsToSkip, 0)
                : Math.min(root.currentIndex + itemsToSkip, root.count - 1);
        }
    }

    highlight: Rectangle {
        color: "#0074da"
        width: root.cellWidth
        height: root.cellHeight
        scale: 1.20
        z: 2
    }
    highlightMoveDuration: 0

    delegate: Item {
        width: root.cellWidth
        height: root.cellHeight
        scale: GridView.isCurrentItem ? 1.20 : 1.0
        z: GridView.isCurrentItem ? 3 : 1
        Behavior on scale { PropertyAnimation { duration: 150 } }

        Image {
            id: coverImage
            anchors { fill: parent; margins: vpx(5) }
            source: coverUrl
            sourceSize { width: 256; height: 256 }
            asynchronous: true
            visible: source != ""
            fillMode: Image.PreserveAspectFit

            onStatusChanged: if (status === Image.Ready && root.currentRecalcs < root.maxRecalcs) {
                root.currentRecalcs++;
                root.updateCellHeightRatio(implicitWidth, implicitHeight);
            }
        }

        Image {
            anchors.centerIn: parent
            visible: coverImage.status === Image.Loading
            source: "../assets/loading-spinner.png"
            RotationAnimator on rotation {
                loops: Animator.Infinite
                from: 0; to: 360; duration: 500
            }
        }

        Text {
            width: parent.width - vpx(32)
            anchors.centerIn: parent
            visible: !coverImage.visible || coverImage.status === Image.Error
            text: title
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
            color: "#eee"
            font { pixelSize: vpx(16); family: globalFonts.sans }
        }

        Rectangle {
            anchors.centerIn: parent
            visible: installed
            color: "#808080"
            width: coverImage.width
            height: coverImage.height
            opacity: 0.4
        }

        Rectangle {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: vpx(-5)
            width: stateLabel.implicitWidth + vpx(14)
            height: stateLabel.implicitHeight + vpx(8)
            radius: vpx(3)
            color: installed ? "#4ae" : "#ff4035"

            Text {
                id: stateLabel
                anchors.centerIn: parent
                text: installed ? "Installiert" : kind
                color: "#eee"
                font { pixelSize: vpx(12); family: globalFonts.sans; bold: true }
            }
        }

        MouseArea {
            anchors.fill: parent
            onClicked: root.currentIndex = index
            onDoubleClicked: {
                root.currentIndex = index;
                root.downloadRequested();
            }
        }
    }
}
