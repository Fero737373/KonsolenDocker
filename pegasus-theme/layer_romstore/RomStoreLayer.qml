// KonsolenDocker ROM Store overlay for the default Pegasus Grid theme.
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick 2.6


FocusScope {
    id: root

    property string currentSystem: ""
    property string collectionName: ""
    property string loadState: "idle"
    property string statusMessage: ""
    property string warningMessage: ""
    property int catalogRequestId: 0
    property string currentJobId: ""
    property string currentJobItemId: ""
    property string currentJobState: ""
    property real jobProgress: 0
    property string jobProgressText: ""
    property string jobMessage: ""
    readonly property bool jobActive: currentJobState === "queued"
                                      || currentJobState === "downloading"
                                      || currentJobState === "installing"
    readonly property var selectedItem: catalogGrid.currentIndex >= 0 && catalogModel.count
                                        ? catalogModel.get(catalogGrid.currentIndex) : null

    signal closeRequested
    signal libraryReloadRequested

    visible: focus
    enabled: focus

    function openFor(system, displayName) {
        currentSystem = system || "";
        collectionName = displayName || system || "Konsole";
        resetJob();
        focus = true;
        loadCatalog();
    }

    function resetJob() {
        currentJobId = "";
        currentJobItemId = "";
        currentJobState = "";
        jobProgress = 0;
        jobProgressText = "";
        jobMessage = "";
    }

    function closeStore() {
        if (jobActive)
            return;
        catalogRequestId++;
        focus = false;
        closeRequested();
    }

    function loadCatalog() {
        requestCatalog("");
    }

    function refreshCatalog() {
        requestCatalog("&refresh=1");
    }

    function requestCatalog(querySuffix) {
        var requestId = ++catalogRequestId;
        loadState = "loading";
        statusMessage = "Freie Inhalte werden geladen …";
        warningMessage = "";
        catalogGrid.resetCells();
        catalogModel.clear();
        request("GET", "/api/v1/catalog?system=" + encodeURIComponent(currentSystem) + querySuffix, null,
            function(status, payload) {
                if (requestId !== catalogRequestId)
                    return;
                if (status !== 200) {
                    loadState = "error";
                    statusMessage = payload.error || "ROM Store ist nicht erreichbar.";
                    return;
                }
                appendCatalogItems(payload.items || []);
                warningMessage = (payload.warnings || []).join(" · ");
                loadState = catalogModel.count ? "ready" : "empty";
                statusMessage = catalogModel.count
                    ? catalogModel.count + " Inhalte verfügbar"
                    : "Für diese Konsole sind aktuell keine freien Inhalte verfügbar.";
                if (catalogModel.count)
                    catalogGrid.currentIndex = 0;
            });
    }

    function appendCatalogItems(items) {
        for (var i = 0; i < items.length; ++i) {
            var item = items[i];
            catalogModel.append({
                "itemId": item.id,
                "title": item.title,
                "kind": item.kind,
                "sourceName": item.source,
                "descriptionText": item.description || "",
                "developerName": item.developer || "",
                "licenseName": item.license || "",
                "coverUrl": item.cover,
                "downloadSize": item.size || 0,
                "installed": item.installed === true
            });
        }
    }

    function startSelectedDownload() {
        if (loadState === "error") {
            refreshCatalog();
            return;
        }
        if (loadState !== "ready" || !selectedItem || jobActive || currentJobState !== "")
            return;
        if (selectedItem.installed)
            return;
        jobMessage = "Download wird vorbereitet …";
        currentJobState = "queued";
        currentJobItemId = selectedItem.itemId;
        request("POST", "/api/v1/download", {"id": selectedItem.itemId},
            function(status, payload) {
                if (status !== 202) {
                    currentJobState = "failed";
                    jobMessage = payload.error || "Download konnte nicht gestartet werden.";
                    return;
                }
                currentJobId = payload.job.id;
                updateJob(payload.job);
                pollTimer.start();
            });
    }

    function cancelDownload() {
        if (!currentJobId || !jobActive)
            return;
        request("POST", "/api/v1/jobs/" + currentJobId + "/cancel", {}, function(status, payload) {
            if (payload.job)
                updateJob(payload.job);
        });
    }

    function pollJob() {
        if (!currentJobId || !jobActive)
            return;
        request("GET", "/api/v1/jobs/" + currentJobId, null, function(status, payload) {
            if (status !== 200) {
                currentJobState = "failed";
                jobMessage = payload.error || "Download-Status ist nicht erreichbar.";
                return;
            }
            updateJob(payload.job);
        });
    }

    function updateJob(job) {
        currentJobState = job.state || "failed";
        currentJobItemId = job.item_id || currentJobItemId;
        jobMessage = job.message || "";
        jobProgress = job.progress === null || job.progress === undefined ? 0 : job.progress;
        jobProgressText = progressText(job);
        if (!jobActive)
            pollTimer.stop();
        if (currentJobState === "completed") {
            markInstalled(currentJobItemId);
            reloadTimer.start();
        }
    }

    function markInstalled(itemId) {
        for (var index = 0; index < catalogModel.count; ++index) {
            if (catalogModel.get(index).itemId === itemId) {
                catalogModel.setProperty(index, "installed", true);
                return;
            }
        }
    }

    function progressText(job) {
        var received = formatBytes(job.downloaded_bytes || 0);
        var total = job.total_bytes ? " / " + formatBytes(job.total_bytes) : "";
        var speed = job.speed_bps ? " · " + formatBytes(job.speed_bps) + "/s" : "";
        return received + total + speed;
    }

    function request(method, path, body, callback) {
        var xhr = new XMLHttpRequest();
        xhr.onreadystatechange = function() {
            if (xhr.readyState !== XMLHttpRequest.DONE)
                return;
            callback(xhr.status, responsePayload(xhr.responseText));
        };
        xhr.open(method, "http://romstore:8080" + path);
        if (body !== null) {
            xhr.setRequestHeader("Content-Type", "application/json");
            xhr.send(JSON.stringify(body));
        } else {
            xhr.send();
        }
    }

    function responsePayload(responseText) {
        try {
            return JSON.parse(responseText || "{}");
        } catch (error) {
            return {"error": "Ungültige Antwort vom ROM Store."};
        }
    }

    function formatBytes(bytes) {
        if (bytes < 1024)
            return bytes + " B";
        if (bytes < 1024 * 1024)
            return (bytes / 1024).toFixed(1) + " KiB";
        if (bytes < 1024 * 1024 * 1024)
            return (bytes / 1024 / 1024).toFixed(1) + " MiB";
        return (bytes / 1024 / 1024 / 1024).toFixed(2) + " GiB";
    }

    Keys.onPressed: {
        if (event.isAutoRepeat)
            return;
        if (api.keys.isCancel(event)) {
            event.accepted = true;
            if (jobActive)
                cancelDownload();
            else
                closeStore();
            return;
        }
        if (api.keys.isAccept(event)) {
            event.accepted = true;
            startSelectedDownload();
            return;
        }
        if (api.keys.isDetails(event) && loadState !== "loading"
                && !jobActive && currentJobState === "") {
            event.accepted = true;
            refreshCatalog();
            return;
        }
        if (api.keys.isFilters(event)) {
            event.accepted = true;
            closeStore();
        }
    }

    ListModel { id: catalogModel }

    Timer {
        id: pollTimer
        interval: 400
        repeat: true
        onTriggered: pollJob()
    }

    Timer {
        id: reloadTimer
        interval: 900
        repeat: false
        onTriggered: libraryReloadRequested()
    }

    Rectangle {
        anchors.fill: parent
        color: "#111"
        opacity: 0.96

        CatalogInfoPanel {
            id: infoPanel
            anchors { top: parent.top; bottom: parent.bottom; left: parent.left }
            width: parent.width * 0.40
            selectedItem: root.selectedItem
            collectionName: root.collectionName
            statusMessage: root.statusMessage
            warningMessage: root.warningMessage
            downloadSizeText: selectedItem && selectedItem.downloadSize
                              ? root.formatBytes(selectedItem.downloadSize) : ""
        }

        CatalogGrid {
            id: catalogGrid
            focus: true
            anchors {
                left: infoPanel.right; leftMargin: vpx(24)
                right: parent.right; rightMargin: vpx(6)
                top: parent.top; topMargin: vpx(32)
                bottom: parent.bottom
            }
            model: catalogModel
            enabled: root.currentJobState === ""
            visible: root.loadState === "ready"
            onDownloadRequested: root.startSelectedDownload()
        }

        CatalogEmptyState {
            anchors.centerIn: catalogGrid
            width: catalogGrid.width * 0.8
            loadState: root.loadState
            statusMessage: root.statusMessage
            warningMessage: root.warningMessage
            visible: root.loadState !== "ready"
        }

        DownloadDialog {
            anchors.fill: parent
            jobState: root.currentJobState
            message: root.jobMessage
            progress: root.jobProgress
            progressText: root.jobProgressText
            active: root.jobActive
        }
    }
}
