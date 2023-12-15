// JS for Web Sockets
// TODO: Look Into Moving Everything Here for Auto Reconnect

console.log('Connecting to WebSocket...')

let socket
let ws

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
        if (toast.isShown()) {
            $('#disconnected-toast-title')
                .removeClass('text-warning')
                .addClass('text-success')
                .text('Connected')
        }
    }
    // socket.onmessage = function (event) {
    //     console.log('socket.onmessage:', event)
    // }
    socket.onclose = function (event) {
        if (![1000, 1001].includes(event.code)) {
            console.warn('WebSocket Disconnected!')
            setTimeout(function () {
                $('#disconnected-toast-title')
                    .removeClass('text-success')
                    .addClass('text-warning')
                    .text('Reconnecting...')
                if (!toast.isShown()) {
                    toast.show()
                }
            }, 2 * 1000)
        }
        setTimeout(function () {
            wsConnect()
        }, 10 * 1000)
    }
    socket.onerror = function (event) {
        console.error('WebSocket Error:', event)
    }
}
wsConnect()
