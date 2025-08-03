// JS for live.html

let pingInterval

document.addEventListener('DOMContentLoaded', () => {
    console.log('DOMContentLoaded: live.js')
    const player = videojs('my-video', {
        // fluid: true,
        fill: true,
        autoplay: 'play',
    })
    console.log('player:', player)
    // setTimeout(pingServer, 1000 * 10)
    // setInterval(pingServer, 1000 * 60)
    // player?.ready(() => {
    //     console.log('%c player?.ready:', 'color: Lime', player)
    // })
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
    const player = videojs.getPlayer('my-video')
    // console.log('player:', player)
    const name = window.location.pathname.split('/')[2]
    if (name && player && !player.paused()) {
        console.log('%c PLAYING:', 'color: Lime')
        if (!pingInterval) {
            console.log('%c setInterval: pingServer', 'color: Lime')
            pingInterval = setInterval(pingServer, 1000 * 58)
        }
        const response = await fetch(`/api/stream/ping/${name}/`)
        console.log('response:', response)
    } else {
        console.log('%c PAUSED or no player:', 'color: OrangeRed', player)
    }
}
