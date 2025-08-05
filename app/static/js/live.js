// JS for live.html

const viewCountText = document.getElementById('view-count')
const streamName = window.location.pathname.split('/')[2]

let checkInterval
let pingInterval
let player

document.addEventListener('DOMContentLoaded', () => {
    console.log(`DOMContentLoaded: live.js - ${streamName}`)
    player = videojs('my-video', {
        // fluid: true,
        fill: true,
        autoplay: 'play',
    })
    console.log('player:', player)
    if (!checkInterval) {
        // noinspection JSIgnoredPromiseFromCall
        checkStream()
        checkInterval = setInterval(checkStream, 1000 * 60)
    }
    player.on('play', () => {
        console.log('%c player.on: play', 'color: Lime')
        // noinspection JSIgnoredPromiseFromCall
        pingServer()
    })
    player.on('stop', () => {
        console.log('%c player.on: stop', 'color: OrangeRed')
        clearInterval(pingInterval)
    })
})

async function pingServer() {
    console.log(`pingServer: ${streamName}:`, player)
    if (streamName && player && !player.paused()) {
        console.log('%c PLAYING:', 'color: Lime')
        if (!pingInterval) {
            console.log('%c setInterval: pingServer', 'color: Lime')
            pingInterval = setInterval(pingServer, 1000 * 58)
        }
        const response = await fetch(`/api/stream/ping/${streamName}/`)
        console.log('response:', response)
    } else {
        console.log('%c PAUSED or NO player:', 'color: OrangeRed', player)
    }
}

async function checkStream() {
    console.log(`checkStream: ${streamName}:`, player)
    const url = `/api/stream/viewers/${streamName}/`
    const options = { headers: { Accept: 'application/json' } }
    fetch(url, options).then((response) => {
        console.log('response:', response)
        if (response.ok) {
            response.json().then((data) => {
                console.log('data:', data)
                viewCountText.textContent = data.count
            })
        }
    })
    // .catch((e) => console.log('checkStream: catch:', e))
}
