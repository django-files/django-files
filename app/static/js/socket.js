console.log('Connecting to WebSocket...')

let socket

$(document).ready(function () {
    function wsConnect() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
        socket = new WebSocket(`${protocol}//${window.location.host}/ws/home/`)
        socket.onopen = function (event) {
            console.log('socket.onopen')
            console.log(event)
            // $('#socketWarning').addClass('d-none')
        }
        socket.onmessage = function (event) {
            console.log('socket.onmessage')
            console.log(event)
            console.log(`Message: ${event.data}`)
        }
        socket.onclose = function (event) {
            console.log(`socket.onclose: ${event.code}`)
            console.log(event)
            if (event.code !== 1000) {
                console.log('Unclean Close, Showing: #socketWarning')
                $('#socketWarning').removeClass('d-none')
            }
            setTimeout(function () {
                wsConnect()
            }, 10 * 1000)
        }
        socket.onerror = function (event) {
            console.error('socket.onerror')
            console.log(event)
            // socket.close()
        }
    }
    wsConnect()
})
