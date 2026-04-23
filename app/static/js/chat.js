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
    socket?.removeEventListener('message', handleMessage)
    socket?.addEventListener('message', handleMessage)
}

const viewerMap = new Map()

function updateViewers(viewers) {
    viewerMap.clear()
    viewers.forEach((v) =>
        viewerMap.set(
            v.viewer_id ?? (v.user_id != null ? String(v.user_id) : v.username),
            v
        )
    )
    renderViewers()
}

function renderViewers() {
    chatViewerCount.textContent = viewerMap.size
    const fragment = document.createDocumentFragment()
    viewerMap.forEach((v) => {
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
        fragment.appendChild(el)
    })
    chatViewersPanel.innerHTML = ''
    chatViewersPanel.appendChild(fragment)
}

// --- Message dispatch ---

function handleHistory(data) {
    if (data.viewer_id) myViewerId = data.viewer_id
    chatMessages.innerHTML = ''
    if (data.messages) {
        data.messages.forEach((msg) => appendMessage(msg))
        chatMessages.scrollTop = chatMessages.scrollHeight
    }
    if (data.viewers) updateViewers(data.viewers)
}

function handleViewerJoined(data) {
    const v = data.viewer
    const key =
        v.viewer_id ?? (v.user_id != null ? String(v.user_id) : v.username)
    viewerMap.set(key, v)
    renderViewers()
}

function handleChatSettings(data) {
    const wasEnabled = liveChatEnabled
    liveChatEnabled = data.live_chat
    applyChatSettings(data)
    if (!wasEnabled && liveChatEnabled) joinChat()
}

function handleMessageCleanup(data) {
    chatMessages.querySelectorAll('.chat-msg').forEach((el) => {
        if (
            el.dataset.username === data.username ||
            (data.user_id != null && el.dataset.userId === String(data.user_id))
        ) {
            el.remove()
        }
    })
}

function handleBanned(data) {
    if (!data.viewer_id || data.viewer_id === myViewerId) applyChatBanned()
}

const MESSAGE_HANDLERS = {
    'chat-message': (data) => appendMessage(data),
    'chat-history': handleHistory,
    'chat-viewers': (data) => updateViewers(data.viewers),
    'chat-viewer-joined': handleViewerJoined,
    'chat-viewer-left': (data) => {
        viewerMap.delete(data.viewer_id)
        renderViewers()
    },
    'chat-settings': handleChatSettings,
    'chat-retry': () => {
        if (joinChatRetries++ < 10) setTimeout(joinChat, 1500 * joinChatRetries)
    },
    'chat-name-set': (data) =>
        appendSystemMessage(`Your name has been set to: ${data.display_name}`),
    'chat-message-cleanup': handleMessageCleanup,
    'chat-banned': handleBanned,
}

function handleMessage(event) {
    let data
    try {
        data = JSON.parse(event.data)
    } catch {
        return
    }
    if (data.name !== streamName) return
    MESSAGE_HANDLERS[data.event]?.(data)
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
document.addEventListener('wsConnected', () => {
    addSocketListener()
    if (liveChatEnabled && !chatManuallyDisconnected) joinChat()
})

// Chat form submit
if (chatForm && chatInput) {
    chatForm.addEventListener('submit', (e) => {
        e.preventDefault()
        const message = chatInput.value.trim()
        if (!message) return
        chatInput.value = ''
        hideAutocomplete()
        if (message.startsWith('/')) {
            executeCommand(message)
            return
        }
        if (chatManuallyDisconnected) {
            appendSystemMessage('You are disconnected. Use /join to rejoin.')
            return
        }
        sendSocket({
            method: 'send-chat-message',
            name: streamName,
            message: message,
        })
    })

    chatInput.addEventListener('input', updateAutocomplete)

    chatInput.addEventListener('keydown', (e) => {
        if (autocompleteEl.style.display === 'none') return
        if (e.key === 'Escape') {
            hideAutocomplete()
            e.preventDefault()
        } else if (e.key === 'ArrowUp') {
            navigateAutocomplete(-1)
            e.preventDefault()
        } else if (e.key === 'ArrowDown') {
            navigateAutocomplete(1)
            e.preventDefault()
        } else if (e.key === 'Tab') {
            e.preventDefault()
            const typed = chatInput.value.split(' ')[0].toLowerCase()
            const matches = visibleCommands().filter((c) =>
                c.command.startsWith(typed)
            )
            const idx = Math.max(0, selectedAutocompleteIndex)
            if (matches[idx]) applyAutocompleteItem(matches[idx])
        }
    })
}

// Toggle viewers panel
if (toggleViewersBtn) {
    toggleViewersBtn.addEventListener('click', () => {
        chatViewersPanel.classList.toggle('d-none')
    })
}

// --- Command system ---

let myViewerId = null
let chatManuallyDisconnected = false

const CHAT_COMMANDS = [
    {
        command: '/set-name',
        args: '<name>',
        description: 'Set your chat display name',
    },
    {
        command: '/leave',
        args: '',
        description: 'Leave chat and hide messages',
    },
    {
        command: '/join',
        args: '',
        description: 'Rejoin chat and resume messages',
        condition: () => chatManuallyDisconnected,
    },
    {
        command: '/title',
        args: '<title>',
        description: 'Set the stream title',
        ownerOnly: true,
    },
    {
        command: '/description',
        args: '<description>',
        description: 'Set the stream description',
        ownerOnly: true,
    },
    {
        command: '/ban',
        args: '<display_name>',
        description: 'Ban a user from chat',
        ownerOnly: true,
    },
    {
        command: '/ban-message-cleanup',
        args: '<display_name>',
        description: "Remove a banned user's messages",
        ownerOnly: true,
    },
]

// Autocomplete element created eagerly — no lazy-init needed
const autocompleteEl = document.createElement('div')
autocompleteEl.id = 'chat-autocomplete'
autocompleteEl.className = 'chat-autocomplete'
autocompleteEl.style.display = 'none'
const inputArea = document.getElementById('chat-input-area')
if (inputArea) inputArea.before(autocompleteEl)

let selectedAutocompleteIndex = -1

function hideAutocomplete() {
    selectedAutocompleteIndex = -1
    autocompleteEl.style.display = 'none'
    autocompleteEl.innerHTML = ''
}

function visibleCommands() {
    return CHAT_COMMANDS.filter(
        (c) => (!c.ownerOnly || isOwner) && (!c.condition || c.condition())
    )
}

function updateAutocomplete() {
    const val = chatInput.value
    if (!val.startsWith('/')) {
        hideAutocomplete()
        return
    }
    const typed = val.split(' ')[0].toLowerCase()
    const matches = visibleCommands().filter((c) => c.command.startsWith(typed))
    if (!matches.length) {
        hideAutocomplete()
        return
    }
    autocompleteEl.style.display = ''
    autocompleteEl.innerHTML = ''
    selectedAutocompleteIndex = Math.min(
        selectedAutocompleteIndex,
        matches.length - 1
    )
    matches.forEach((c, i) => {
        const item = document.createElement('div')
        item.className =
            'chat-autocomplete-item' +
            (i === selectedAutocompleteIndex ? ' active' : '')
        item.dataset.index = i
        item.title = `${c.command} ${c.args} — ${c.description}`.trim()

        const cmd = document.createElement('strong')
        cmd.className = 'me-1'
        cmd.textContent = c.command

        const args = document.createElement('span')
        args.className = 'text-muted me-1'
        args.textContent = c.args

        const desc = document.createElement('span')
        desc.className = 'text-secondary'
        desc.textContent = '— ' + c.description

        item.appendChild(cmd)
        item.appendChild(args)
        item.appendChild(desc)

        item.addEventListener('mousedown', (e) => {
            e.preventDefault()
            applyAutocompleteItem(c)
        })
        autocompleteEl.appendChild(item)
    })
}

function applyAutocompleteItem(c) {
    // If the user already typed args, keep them; otherwise set cursor after command
    const parts = chatInput.value.split(' ')
    if (parts.length > 1) {
        chatInput.value = c.command + ' ' + parts.slice(1).join(' ')
    } else {
        chatInput.value = c.command + ' '
    }
    hideAutocomplete()
    chatInput.focus()
}

function navigateAutocomplete(dir) {
    if (autocompleteEl.style.display === 'none') return false
    const items = autocompleteEl.querySelectorAll('.chat-autocomplete-item')
    if (!items.length) return false
    selectedAutocompleteIndex = Math.max(
        0,
        Math.min(items.length - 1, selectedAutocompleteIndex + dir)
    )
    items.forEach((el, i) =>
        el.classList.toggle('active', i === selectedAutocompleteIndex)
    )
    return true
}

function cmdSetName(args) {
    const customName = args.join(' ').trim()
    if (!customName) {
        appendSystemMessage('Usage: /set-name <your name>')
        return
    }
    if (customName.length > 32) {
        appendSystemMessage('Name too long. Maximum 32 characters.')
        return
    }
    sendSocket({
        method: 'set-chat-name',
        name: streamName,
        custom_name: customName,
    })
}

function cmdSetTitle(args) {
    if (!isOwner) {
        appendSystemMessage('You do not have permission to use this command.')
        return
    }
    const title = args.join(' ').trim()
    if (!title) {
        appendSystemMessage('Usage: /title <title>')
        return
    }
    sendSocket({ method: 'set-stream-title', name: streamName, title })
}

function cmdSetDescription(args) {
    if (!isOwner) {
        appendSystemMessage('You do not have permission to use this command.')
        return
    }
    const description = args.join(' ').trim()
    if (!description) {
        appendSystemMessage('Usage: /description <description>')
        return
    }
    sendSocket({
        method: 'set-stream-description',
        name: streamName,
        description,
    })
}

function cmdBan(args) {
    if (!isOwner) {
        appendSystemMessage('You do not have permission to use this command.')
        return
    }
    const target = args.join(' ').trim()
    if (!target) {
        appendSystemMessage('Usage: /ban <display_name>')
        return
    }
    sendSocket({ method: 'ban-chat-user', name: streamName, target })
}

function cmdBanMessageCleanup(args) {
    if (!isOwner) {
        appendSystemMessage('You do not have permission to use this command.')
        return
    }
    const target = args.join(' ').trim()
    if (!target) {
        appendSystemMessage('Usage: /ban-message-cleanup <display_name>')
        return
    }
    sendSocket({ method: 'ban-message-cleanup', name: streamName, target })
}

const COMMAND_DISPATCH = {
    '/set-name': cmdSetName,
    '/leave': () => chatDisconnect(),
    '/join': () => chatReconnect(),
    '/title': cmdSetTitle,
    '/description': cmdSetDescription,
    '/ban': cmdBan,
    '/ban-message-cleanup': cmdBanMessageCleanup,
}

function executeCommand(input) {
    const parts = input.trim().split(/\s+/)
    const cmd = parts[0].toLowerCase()
    const handler = COMMAND_DISPATCH[cmd]
    if (handler) {
        handler(parts.slice(1))
    } else {
        appendSystemMessage(
            `Unknown command: ${cmd}. Type / to see available commands.`
        )
    }
}

function appendSystemMessage(text) {
    const el = document.createElement('div')
    el.className = 'chat-system-msg small text-secondary fst-italic px-1 py-0'
    el.textContent = text
    chatMessages.appendChild(el)
    chatMessages.scrollTop = chatMessages.scrollHeight
}

function applyChatBanned() {
    const inputArea = document.getElementById('chat-input-area')
    const loginPrompt = document.getElementById('chat-login-prompt')
    if (inputArea) inputArea.style.display = 'none'
    if (loginPrompt) loginPrompt.style.display = 'none'
    hideAutocomplete()
    const existing = document.getElementById('chat-banned-notice')
    if (existing) return
    const notice = document.createElement('div')
    notice.id = 'chat-banned-notice'
    notice.className = 'chat-input-area px-3 py-2 border-top text-center'
    notice.innerHTML =
        '<small class="text-danger">You have been banned from this chat.</small>'
    const liveChat = document.getElementById('live-chat')
    if (liveChat) liveChat.appendChild(notice)
}

function chatDisconnect() {
    if (chatManuallyDisconnected) {
        appendSystemMessage('Already disconnected. Use /join to rejoin.')
        return
    }
    chatManuallyDisconnected = true
    socket?.removeEventListener('message', handleMessage)
    sendSocket({ method: 'leave-stream-chat', name: streamName })
    viewerMap.clear()
    renderViewers()
    chatMessages.innerHTML = ''
    hideAutocomplete()
    if (chatInput) chatInput.placeholder = 'Type /join to rejoin...'
    const notice = document.createElement('div')
    notice.id = 'chat-disconnected-notice'
    notice.className =
        'chat-system-msg small text-secondary fst-italic text-center py-3'
    notice.textContent =
        'You have disconnected from chat. Type /join to rejoin.'
    chatMessages.appendChild(notice)
}

function chatReconnect() {
    if (document.getElementById('chat-banned-notice')) {
        appendSystemMessage('You are banned from this chat.')
        return
    }
    if (!chatManuallyDisconnected) {
        appendSystemMessage('Already connected.')
        return
    }
    chatManuallyDisconnected = false
    if (chatInput) chatInput.placeholder = 'Send a message...'
    addSocketListener()
    joinChat()
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
    el.dataset.username = msg.username
    if (msg.user_id != null) el.dataset.userId = msg.user_id

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
