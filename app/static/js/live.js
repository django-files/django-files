// JS for live.html

const viewCountText = document.getElementById('view-count')
const subscriberCountText = document.getElementById('subscriber-count')
const streamName = window.location.pathname.split('/')[2]

let checkInterval
let pingInterval
let player
let lastSubscriberCount = null

const SUBSCRIBER_POLL_BASE_MS = 5 * 60 * 1000 // 5 minutes
const SUBSCRIBER_POLL_JITTER_MS = 60 * 1000 // ± 1 minute

function subscriberPollDelay() {
    return (
        SUBSCRIBER_POLL_BASE_MS +
        Math.round((Math.random() * 2 - 1) * SUBSCRIBER_POLL_JITTER_MS)
    )
}

document.addEventListener('DOMContentLoaded', () => {
    console.log(`DOMContentLoaded: live.js - ${streamName}`)
    player = videojs('my-video', {
        fill: true,
        liveTracker: {
            trackingThreshold: 0,
        },
        html5: {
            vhs: {
                liveSyncDurationCount: 2,
            },
        },
    })
    console.log('player:', player)
    if (!checkInterval) {
        // noinspection JSIgnoredPromiseFromCall
        checkStream()
        checkInterval = setInterval(checkStream, 1000 * 60)
    }
    checkSubscribers()
    scheduleSubscriberCheck()
    player.on('play', () => {
        console.log('%c player.on: play', 'color: Lime')
        // noinspection JSIgnoredPromiseFromCall
        pingServer()
    })
    player.on('stop', () => {
        console.log('%c player.on: stop', 'color: OrangeRed')
        clearInterval(pingInterval)
    })
    player.on('error', (error) => {
        console.error('Video player error:', error)
        window.openSidebar()
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
    const options = { headers: { Accept: 'application/json' } }
    fetch(`/api/stream/viewers/${streamName}/`, options).then((response) => {
        console.log('response:', response)
        if (response.ok) {
            response.json().then((data) => {
                console.log('data:', data)
                viewCountText.textContent = data.count
            })
        }
    })
}

function checkSubscribers() {
    const options = { headers: { Accept: 'application/json' } }
    fetch(`/api/stream/subscribers/${streamName}/`, options).then(
        (response) => {
            if (response.ok) {
                response.json().then((data) => {
                    if (data.count !== lastSubscriberCount) {
                        lastSubscriberCount = data.count
                        if (subscriberCountText)
                            subscriberCountText.textContent = data.count
                    }
                })
            }
        }
    )
}

function scheduleSubscriberCheck() {
    const delay = subscriberPollDelay()
    console.log(
        `scheduleSubscriberCheck: next check in ${(delay / 1000).toFixed(0)}s`
    )
    setTimeout(() => {
        checkSubscribers()
        scheduleSubscriberCheck()
    }, delay)
}
