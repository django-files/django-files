// JS for Web Sockets

console.log('Connecting to WebSocket...')

let socket
let ws

function wsConnect() {
    if (ws) {
        console.log('closing existing connection')
        ws.close()
    }
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    socket = new WebSocket(`${protocol}//${window.location.host}/ws/home/`)
    socket.onopen = function (event) {
        console.log('socket.onopen:', event)
        // $('#socket-warning').addClass('d-none')
    }
    // socket.onmessage = function (event) {
    //     console.log('socket.onmessage:', event)
    //     console.log(`Message: ${event.data}`)
    // }
    socket.onclose = function (event) {
        console.log(`socket.onclose: ${event.code}:`, event)
        if (![1000, 1001].includes(event.code)) {
            setTimeout(function () {
                console.log('Unclean Close, Showing Socket Warnings')
                $('#socket-warning').removeClass('d-none')
                let toastEl = $('#disconnected-toast')
                if (toastEl.length) {
                    let toast = bootstrap.Toast.getOrCreateInstance(toastEl)
                    if (!toast.isShown()) {
                        toast.show()
                    }
                }
            }, 2 * 1000)
        }
        setTimeout(function () {
            wsConnect()
        }, 10 * 1000)
    }
    socket.onerror = function (event) {
        console.error('socket.onerror:', event)
        // socket.close()
    }
}
wsConnect()
