// WebSocket JS

console.log('Connecting to WebSocket...')

const socket = connect()

function connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/home/`)

    ws.onopen = function () {
        console.log('Socket Open')
    }

    ws.onmessage = function (event) {
        console.log(`Socket Message: ${event.data}`)
    }

    ws.onclose = function (event) {
        console.log(`Socket Close: ${event.reason}`)
        setTimeout(function () {
            console.log('Reconnecting...')
            connect()
        }, 15000)
    }

    ws.onerror = function (event) {
        console.error('Socket Error')
        console.log(event)
        // ws.close()
    }

    return ws
}
