// WebSocket JS

console.log('Connecting to WebSocket...')

const socket = connect()

function connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/home/`)

    ws.onopen = function () {
        console.log('Socket Open')
        $('#socketWarning').addClass('d-none')
    }

    ws.onmessage = function (event) {
        console.log(`Socket Message: ${event.data}`)
    }

    ws.onclose = function (event) {
        console.log(`Socket Close: ${event.code}: ${event.reason}`)
        if (event.code !== 1000) {
            $('#socketWarning').removeClass('d-none')
        }
        console.log(event)
        setTimeout(function () {
            console.log('Reconnecting...')
            connect()
        }, 10000)
    }

    ws.onerror = function (event) {
        console.error('Socket Error')
        console.log(event)
        // ws.close()
    }

    return ws
}
