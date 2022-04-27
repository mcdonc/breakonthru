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
    if (typeof ws !== 'undefined') {
        printLog("websocket already created, not creating another")
        return
    }
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

function printLog(msg) {
    var log = document.getElementById('log')
    log.value += msg + '\n'
    log.scrollTop = log.scrollHeight
}


