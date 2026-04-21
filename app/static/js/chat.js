// JS for live chat on live.html
// Uses the shared WebSocket from socket.js for real-time chat messaging

import { socket } from './socket.js'

const config = globalThis.chatConfig
if (!config?.streamName) {
    throw new Error('Chat config not found')
}

const streamName = config.streamName
const userInfo = config.userInfo
const isOwner = config.isOwner || false
const ownerUserId = config.ownerUserId
let liveChatEnabled = config.liveChatEnabled

const CHAT_COLORS = [
    '#dc3545', // red
    '#198754', // green
    '#0d6efd', // blue
    '#ffc107', // yellow
    '#6f42c1', // purple
    '#6610f2', // indigo
    '#0dcaf0', // cyan
    '#fd7e14', // orange
]

function getUserColor(key) {
    let hash = 0
    for (let i = 0; i < key.length; i++) {
        hash = Math.trunc((hash << 5) - hash + key.codePointAt(i))
    }
    return CHAT_COLORS[Math.abs(hash) % CHAT_COLORS.length]
}

const chatMessages = document.getElementById('chat-messages')
const chatForm = document.getElementById('chat-form')
const chatInput = document.getElementById('chat-input')
const chatViewerCount = document.getElementById('chat-viewer-count')
const chatViewersPanel = document.getElementById('chat-viewers-panel')
const toggleViewersBtn = document.getElementById('toggleViewers')

function sendSocket(data) {
    if (socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(data))
        return true
    }
    return false
}

let joinChatRetries = 0
function joinChat() {
    joinChatRetries = 0
    sendSocket({ method: 'join-stream-chat', name: streamName })
}

// Wait for socket to connect, then join
function initChat() {
    if (socket?.readyState === WebSocket.OPEN) {
        if (liveChatEnabled) joinChat()
        addSocketListener()
    } else {
        setTimeout(initChat, 500)
    }
}

function addSocketListener() {
    socket?.addEventListener('message', handleMessage)
}

function handleMessage(event) {
    let data
    try {
        data = JSON.parse(event.data)
    } catch {
        return
    }
    if (data.name !== streamName) return

    if (data.event === 'chat-message') {
        appendMessage(data)
    } else if (data.event === 'chat-history') {
        chatMessages.innerHTML = ''
        if (data.messages) {
            data.messages.forEach((msg) => appendMessage(msg))
            chatMessages.scrollTop = chatMessages.scrollHeight
        }
    } else if (data.event === 'chat-viewers') {
        updateViewers(data.viewers)
    } else if (data.event === 'chat-settings') {
        const wasEnabled = liveChatEnabled
        liveChatEnabled = data.live_chat
        applyChatSettings(data)
        if (!wasEnabled && liveChatEnabled) {
            joinChat()
        }
    } else if (data.event === 'chat-retry') {
        if (joinChatRetries++ < 10) setTimeout(joinChat, 1500 * joinChatRetries)
    }
}

function updateAnonInput(anonymousChat) {
    const inputArea = document.getElementById('chat-input-area')
    const loginPrompt = document.getElementById('chat-login-prompt')
    if (inputArea) inputArea.style.display = anonymousChat ? '' : 'none'
    if (loginPrompt) loginPrompt.style.display = anonymousChat ? 'none' : ''
}

function applyChatSettings(data) {
    document
        .getElementById('live-chat')
        ?.classList.toggle('chat-hidden', !data.live_chat)

    const infoCard = document.getElementById('stream-info-card')
    if (infoCard) {
        infoCard.classList.toggle('sidebar-card-with-chat', true)
        infoCard.classList.toggle('flex-grow-1', false)
    }

    const anonWrapper = document.getElementById('anonChatToggleWrapper')
    if (anonWrapper) {
        anonWrapper.style.opacity = data.live_chat ? '1' : '0.5'
        anonWrapper.style.pointerEvents = data.live_chat ? '' : 'none'
    }

    const toggleLiveChatEl = document.getElementById('toggleLiveChat')
    if (toggleLiveChatEl) toggleLiveChatEl.checked = data.live_chat

    const toggleAnonChatEl = document.getElementById('toggleAnonChat')
    if (toggleAnonChatEl) toggleAnonChatEl.checked = data.anonymous_chat

    if (!userInfo.user_id) updateAnonInput(data.anonymous_chat)
}

initChat()

// Chat form submit
if (chatForm && chatInput) {
    chatForm.addEventListener('submit', (e) => {
        e.preventDefault()
        const message = chatInput.value.trim()
        if (!message) return
        sendSocket({
            method: 'send-chat-message',
            name: streamName,
            message: message,
        })
        chatInput.value = ''
    })
}

// Toggle viewers panel
if (toggleViewersBtn) {
    toggleViewersBtn.addEventListener('click', () => {
        chatViewersPanel.classList.toggle('d-none')
    })
}

// Owner controls
if (isOwner) {
    const toggleLiveChatEl = document.getElementById('toggleLiveChat')
    const toggleAnonChatEl = document.getElementById('toggleAnonChat')

    if (toggleLiveChatEl) {
        toggleLiveChatEl.addEventListener('change', () => {
            sendSocket({
                method: 'set-stream-live-chat',
                name: streamName,
                enabled: toggleLiveChatEl.checked,
            })
        })
    }

    if (toggleAnonChatEl) {
        toggleAnonChatEl.addEventListener('change', () => {
            sendSocket({
                method: 'set-stream-anonymous-chat',
                name: streamName,
                enabled: toggleAnonChatEl.checked,
            })
        })
    }
}

function appendMessage(msg) {
    const el = document.createElement('div')
    el.className = 'chat-msg d-flex align-items-start gap-1 mb-1'

    const avatar = document.createElement('img')
    avatar.src = msg.avatar_url
    avatar.className = 'rounded-circle flex-shrink-0'
    avatar.width = 20
    avatar.height = 20
    avatar.alt = msg.username

    const body = document.createElement('div')
    body.className = 'chat-msg-body small'

    const isOwnerMsg = msg.user_id === ownerUserId
    if (isOwnerMsg) {
        const star = document.createElement('i')
        star.className = 'fa-solid fa-star me-1 text-warning'
        star.style.fontSize = '0.75em'
        body.appendChild(star)
    }

    const name = document.createElement('strong')
    name.className = 'chat-msg-name'
    if (isOwnerMsg) {
        name.classList.add('text-info')
    } else {
        const colorKey = msg.user_id ? String(msg.user_id) : msg.username
        name.style.color = getUserColor(colorKey)
    }
    name.textContent = msg.display_name

    const text = document.createElement('span')
    text.className = 'chat-msg-text'
    text.textContent = msg.message

    body.appendChild(name)
    body.appendChild(document.createTextNode(' '))
    body.appendChild(text)
    el.appendChild(avatar)
    el.appendChild(body)
    chatMessages.appendChild(el)

    // Auto-scroll if near bottom
    const isNearBottom =
        chatMessages.scrollHeight -
            chatMessages.scrollTop -
            chatMessages.clientHeight <
        60
    if (isNearBottom || msg.user_id === userInfo.user_id) {
        chatMessages.scrollTop = chatMessages.scrollHeight
    }
}

function updateViewers(viewers) {
    chatViewerCount.textContent = viewers.length
    chatViewersPanel.innerHTML = ''
    viewers.forEach((v) => {
        const el = document.createElement('div')
        el.className = 'd-flex align-items-center gap-1 mb-1'

        const avatar = document.createElement('img')
        avatar.src = v.avatar_url
        avatar.className = 'rounded-circle'
        avatar.width = 18
        avatar.height = 18
        avatar.alt = v.username

        const name = document.createElement('small')
        name.className = 'fw-semibold'
        name.textContent = v.display_name

        el.appendChild(avatar)
        el.appendChild(name)
        chatViewersPanel.appendChild(el)
    })
}
