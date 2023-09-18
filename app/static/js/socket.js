// WebSocket JS

console.log('Connecting to WebSocket...')

let socket

const socketMessageListener = (event) => {
    console.log(event.data)
}

const socketOpenListener = (event) => {
    console.log('Connected')
    socket.send(event)
    $('#socketWarning').addClass('d-none')
}

const socketCloseListener = (event) => {
    if (socket && event.code !== 1000) {
        console.error('Disconnected.')
        $('#socketWarning').removeClass('d-none')
    }
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    socket = new WebSocket(`${protocol}//${window.location.host}/ws/home/`)
    socket.addEventListener('open', socketOpenListener)
    socket.addEventListener('message', socketMessageListener)
    socket.addEventListener('close', socketCloseListener)
}

socketCloseListener()
