function logout() {
    document.location = "/logout"
}

function buzzDoor() {
    createWebSocket()
    unlockDoor()
}

function unlockDoor() {
    if (window.identified === undefined) {
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

function reenableBuzzButton() {
    buzzbutton = document.getElementById('buzz')
    buzzbutton.disabled = false
    buzzbutton.textContent = "Buzz Front Door"
}

function disableBuzzButton() {
    buzzbutton = document.getElementById('buzz')
    buzzbutton.disabled = true
    buzzbutton.textContent = "... Buzzing ..."
}

function createWebSocket() {
    if (typeof ws !== 'undefined') {
        if (ws.readyState !== WebSocket.CLOSED  ||
            ws.readyState !== WebSocket.CLOSING) {
            return
        }
    }
    url = websocket_url; // from index.pt
    ws = new WebSocket(url)
    ws.onmessage = function(event) {
        var message = JSON.parse(event.data)
        if (message["type"] === "ack") {
            body = message["body"]
            if (body.startsWith("enqueued unlock")) {
                disableBuzzButton();
            }
            if (body.startsWith("door relocked")) {
                reenableBuzzButton();
            }
            printLog(message["body"])
        }
    }
    ws.onclose = function(event) {
        ws = undefined
        window.tokendata = undefined
        window.identified = undefined
        printLog("websocket closed")
    }
    ws.onopen = function(event) {
        printLog("websocket opened")
        fetchTokendata();
        identify()
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

function identify() {
    window.identified = undefined
    if (window.tokendata === undefined) {
        setTimeout(identify, 100)
    }
    else {
        printLog("identifying")
        ws.send(JSON.stringify(
            {"type":"identification",
             "body":"webclient",
             "user":window.tokendata["user"],
             "token":window.tokendata["token"]}
              )
         )
        window.identified = true;
    }
}

function printLog(msg) {
    let current = new Date();
    t = current.toLocaleTimeString()
    d = current.toLocaleDateString()
    var log = document.getElementById('log')
    log.value += d + " " + t + " " + msg + '\n'
    log.scrollTop = log.scrollHeight
}
