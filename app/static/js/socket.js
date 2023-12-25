// JS for Web Sockets
// TODO: Look Into Moving Everything Here for Auto Reconnect

let disconnected = false
let socket
let ws

console.log('Connecting to WebSocket...')
wsConnect()

function wsConnect() {
    if (ws) {
        console.warn('Closing Existing WebSocket Connection!')
        ws.close()
    }
    const toast = bootstrap.Toast.getOrCreateInstance($('#disconnected-toast'))
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    socket = new WebSocket(`${protocol}//${window.location.host}/ws/home/`)
    socket.onopen = function (event) {
        console.log('WebSocket Connected.', event)
        disconnected = false
        if (toast.isShown()) {
            $('#disconnected-toast-title')
                .removeClass('text-danger')
                .addClass('text-warning')
                .text('Connected')
        }
    }
    // socket.onmessage = function (event) {
    //     console.log('socket.onmessage:', event)
    // }
    socket.onclose = function (event) {
        if (![1000, 1001].includes(event.code)) {
            if (!disconnected) {
                console.warn('WebSocket Disconnected!', event)
            }
            if (!toast.isShown()) {
                setTimeout(function () {
                    disconnected = true
                    $('#disconnected-toast-title')
                        .removeClass('text-warning')
                        .addClass('text-danger')
                        .text('Reconnecting...')
                    toast.show()
                }, 2 * 1000)
            }
        }
        setTimeout(function () {
            wsConnect()
        }, 10 * 1000)
    }
    socket.onerror = function (event) {
        if (!disconnected) {
            console.error('WebSocket Error:', event)
        }
    }
}
