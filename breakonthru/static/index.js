function logout() {
    document.location = "/logout"
}

function buzzDoor() {
    createWebSocket()
    unlockDoor()
}

function unlockDoor() {
    if (window.tokendata === undefined) {
        setTimeout(unlockDoor, 100)
    }
    else {
        var unlockdata = JSON.stringify(
            {"type":"unlock",
             "body":window.tokendata["user"]}
        )
        if (ws.readyState === WebSocket.OPEN) {
            ws.send(unlockdata)
        } else if (ws.readyState == WebSocket.CONNECTING) {
            ws.addEventListener('open', () => ws.send(unlockdata))
        }
    }
}

function fetchTokendata() {
    window.tokendata = undefined
    printLog("fetching token data")
    var url = "/token"
    fetch(url).then(
        response=>{return response.json()}
    ).then(
        data=> window.tokendata = data
    )
}

function createWebSocket() {
    if (typeof ws !== 'undefined') { return }
    url = websocket_url; // from index.pt
    ws = new WebSocket(url)
    ws.onmessage = function(event) {
        printLog("got websocket answer message")
        var message = JSON.parse(event.data)
        if (message["type"] === "answer") {
            document.getElementById('answer').value = message["body"]
            startSession()
        }
    }
    ws.onclose = function(event) {
        printLog("Websocket closed")
    }
    ws.onopen = function(event) {
        printLog("Websocket opened")
        fetchTokendata();
        identify()
    }
}

function identify() {
    if (window.tokendata === undefined) {
        setTimeout(identify, 100)
    }
    else {
        ws.send(JSON.stringify(
            {"type":"identification",
             "body":"webclient",
             "user":window.tokendata["user"],
             "token":window.tokendata["token"]}))
    }
}

function createSession() {
    stopSession()
    createWebSocket()
    printLog('Creating session...')
    pc = new RTCPeerConnection({
        'iceServers': [{ 'url': 'stun:stun.l.google.com:19302' }]
    })
    pc.ontrack = function(event) {
        printLog('Accepting new track')
        var el = document.createElement(event.track.kind)
        el.srcObject = event.streams[0]
        el.autoplay = true
        el.controls = true
        document.getElementById('tracks').appendChild(el)
    }
    pc.oniceconnectionstatechange = function(event) {
        printLog('ICE connection state changed to '+pc.iceConnectionState)
    }
    pc.addTransceiver('audio', {'direction': 'sendrecv'})
    mediaOpts = {
        audio: true,
        video: false,
    }
    navigator.mediaDevices.getUserMedia(mediaOpts).then(addMic).catch(skipMic)
}

function addMic(stream) {
    printLog('Adding microphone to session...')
    var track = stream.getTracks()[0]
    pc.addTrack(track, stream)
    createOffer()
}

function skipMic(err) {
    printLog('Skipping microphone configuration: '+err)
    createOffer()
}

function createOffer() {
    var offerOpts = {
        'mandatory': {
            'OfferToReceiveAudio': true,
            'OfferToReceiveVideo': false,
        },
    }
    pc.createOffer(offerOpts).then(setLocalDescription).catch(printLog)
}

function setLocalDescription(offer) {
    pc.setLocalDescription(offer).then(setOffer)
}

function setOffer(offer) {
    var offerbody = pc.localDescription.sdp
    document.getElementById('offer').value = offerbody
    var offerdata = JSON.stringify({"type":"offer", "body":offerbody})
    printLog("sending offer data to websocket server ")
    if (ws.readyState === WebSocket.OPEN) {
        ws.send(offerdata)
    } else if (ws.readyState == WebSocket.CONNECTING) {
        ws.addEventListener('open', () => ws.send(offerdata))
    }
}

function startSession() {
    document.getElementById("talk").disabled = true;
    document.getElementById("hangup").disabled = false;
    var answer = document.getElementById('answer').value
    if (answer === '') {
        return printLog('Error: SDP answer is not set')
    }
    printLog('Starting session...')
    var desc = new RTCSessionDescription({
        'type': 'answer',
        'sdp': answer,
    })
    pc.setRemoteDescription(desc).catch(printLog)
}

function stopSession() {
    if (typeof pc === 'undefined') {
        return
    }
    document.getElementById("talk").disabled = false;
    document.getElementById("hangup").disabled = true;
    printLog('Stopping session...')
    // below is to turn off microphone (simply closing and deleting pc leaves it open)
    var perstream = function(stream) {
        var stop = function(t) {
            t.stop();
        }
        stream.getAudioTracks().map(stop);
    }
    var streams = pc.getLocalStreams()
    streams.map(perstream)
    pc.close()
    delete(pc)
    document.getElementById('offer').value = ''
    document.getElementById('answer').value = ''
    document.getElementById('tracks').innerHTML = ''
    stopWebSocket()
}

function stopWebSocket() {
    if (typeof ws === 'undefined') {
        return
    }
    ws.close()
    delete(ws)
}


function printLog(msg) {
    var log = document.getElementById('log')
    log.value += msg + '\n'
    log.scrollTop = log.scrollHeight
}


