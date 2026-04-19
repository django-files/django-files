// JS for live chat on live.html
// Uses the shared WebSocket from socket.js for real-time chat messaging

import { socket } from './socket.js'

const config = window.chatConfig
if (!config || !config.liveChatEnabled) {
    throw new Error('Chat config not found')
}

const streamName = config.streamName
const userInfo = config.userInfo

const chatMessages = document.getElementById('chat-messages')
const chatForm = document.getElementById('chat-form')
const chatInput = document.getElementById('chat-input')
const chatViewerCount = document.getElementById('chat-viewer-count')
const chatViewersPanel = document.getElementById('chat-viewers-panel')
const toggleViewersBtn = document.getElementById('toggleViewers')

function sendSocket(data) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(data))
        return true
    }
    return false
}

function joinChat() {
    sendSocket({ method: 'join-stream-chat', name: streamName })
}

// Wait for socket to connect, then join
function initChat() {
    if (socket && socket.readyState === WebSocket.OPEN) {
        joinChat()
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
    }
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

function appendMessage(msg) {
    const el = document.createElement('div')
    el.className = 'chat-msg d-flex align-items-start gap-1 mb-1'

    const avatar = document.createElement('img')
    avatar.src = msg.avatar_url
    avatar.className = 'rounded-circle flex-shrink-0 mt-1'
    avatar.width = 20
    avatar.height = 20
    avatar.alt = msg.username

    const body = document.createElement('div')
    body.className = 'chat-msg-body small'

    const name = document.createElement('strong')
    name.className = 'chat-msg-name me-1'
    name.textContent = msg.display_name

    const text = document.createElement('span')
    text.className = 'chat-msg-text'
    text.textContent = msg.message

    body.appendChild(name)
    body.appendChild(text)
    el.appendChild(avatar)
    el.appendChild(body)
    chatMessages.appendChild(el)

    // Auto-scroll if near bottom
    const isNearBottom =
        chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight < 60
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
