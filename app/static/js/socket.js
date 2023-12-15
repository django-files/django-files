// JS for Web Sockets
// TODO: Move Everything Here for Auto Reconnect

console.log('Connecting to WebSocket...')

let socket
let ws
let disconnected = false

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
        if (disconnected) {
            show_toast('Reconnected to Server!', 'success', '15000')
        }
    }
    // socket.onmessage = function (event) {
    //     console.log('socket.onmessage:', event)
    // }
    socket.onclose = function (event) {
        // console.log(`socket.onclose: event.code: ${event.code}`)
        if (![1000, 1001].includes(event.code)) {
            setTimeout(function () {
                console.warn('WebSocket Disconnected:', event)
                if (!toast.isShown()) {
                    // console.log('Showing Disconnect Toast:', toast)
                    toast.show()
                    disconnected = true
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
