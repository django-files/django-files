// Click delegation for album context-menu actions emitted by albums-table.js.
// Mirrors streams-actions.js so both surfaces stay consistent.

import { socket } from './socket.js'

function flashCopiedIcon(btn) {
    const icon = btn.querySelector('i')
    if (!icon) return
    const orig = icon.className
    icon.className = 'fa-solid fa-check fa-fw me-2'
    setTimeout(() => {
        icon.className = orig
    }, 2000)
}

async function onCopyLink(btn) {
    const url = btn.dataset.albumUrl
    if (!url) return
    try {
        await navigator.clipboard.writeText(url)
        flashCopiedIcon(btn)
        if (typeof show_toast === 'function')
            show_toast('Album link copied to clipboard.', 'info', '3000')
    } catch {
        if (typeof show_toast === 'function')
            show_toast('Failed to copy link.', 'danger', '4000')
    }
}

function onTogglePrivate(btn) {
    const pk = btn.dataset.albumId
    if (!pk) return
    const makePrivate =
        btn.dataset.private === 'false' || btn.dataset.private === false
    socket.send(
        JSON.stringify({
            method: 'private_albums',
            pks: [Number.parseInt(pk)],
            private: makePrivate,
        })
    )
}

function onSetPassword(btn) {
    const pk = btn.dataset.albumId
    if (!pk) return
    const modalEl = document.getElementById('albumPasswordModal')
    if (!modalEl) return
    const current =
        btn
            .closest('.album-ctx-menu')
            ?.querySelector('input[name=current-album-password]')?.value || ''
    modalEl.querySelector('input[name=pk]').value = pk
    const input = modalEl.querySelector('input[name=password]')
    input.value = current
    input.type = 'text'
    bootstrap.Modal.getOrCreateInstance(modalEl).show()
}

document
    .getElementById('modal-album-password-form')
    ?.addEventListener('submit', function (event) {
        event.preventDefault()
        const form = event.currentTarget
        const pk = Number.parseInt(form.elements.pk.value)
        const password = form.elements.password.value
        if (!pk) return
        socket.send(
            JSON.stringify({ method: 'set_album_password', pk, password })
        )
        // Optimistically sync the in-DOM hidden input + menu label between
        // Set/Change without waiting on the websocket roundtrip.
        document
            .querySelectorAll(
                `.album-ctx-menu[data-album-id="${CSS.escape(String(pk))}"] input[name=current-album-password]`
            )
            .forEach((el) => {
                el.value = password
            })
        document
            .querySelectorAll(
                `.album-set-password-btn[data-album-id="${CSS.escape(String(pk))}"]`
            )
            .forEach((el) => {
                el.dataset.hasPassword = password ? 'true' : 'false'
                const textNode = [...el.childNodes].find(
                    (n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim()
                )
                if (textNode)
                    textNode.textContent = password
                        ? 'Change Password'
                        : 'Set Password'
            })
        const modalEl = document.getElementById('albumPasswordModal')
        if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).hide()
    })

document
    .getElementById('album-password-unmask')
    ?.addEventListener('click', function () {
        const input = document.getElementById('album-password-input')
        input.type = input.type === 'password' ? 'text' : 'password'
    })

document
    .getElementById('album-password-copy')
    ?.addEventListener('click', async function () {
        const input = document.getElementById('album-password-input')
        if (!input.value) return
        try {
            await navigator.clipboard.writeText(input.value)
            if (typeof show_toast === 'function')
                show_toast('Password copied to clipboard.', 'info', '3000')
        } catch {
            /* clipboard denied */
        }
    })

document
    .getElementById('album-password-generate')
    ?.addEventListener('click', function () {
        const bytes = new Uint8Array(12)
        crypto.getRandomValues(bytes)
        const input = document.getElementById('album-password-input')
        input.value = btoa(String.fromCodePoint(...bytes))
            .replace(/[+/=]/g, '')
            .slice(0, 16)
        input.type = 'text'
    })

function onDelete(btn) {
    // The delete handler is owned by albums-table.js (it holds the wired
    // delete modal instance). Dispatch a custom event it listens for so we
    // don't duplicate modal wiring here.
    const pk = btn.dataset.hookId
    if (!pk) return
    document.dispatchEvent(
        new CustomEvent('album-ctx-delete', { detail: { pk } })
    )
}

const HANDLERS = {
    'album-copy-link-btn': onCopyLink,
    'album-toggle-private-btn': onTogglePrivate,
    'album-set-password-btn': onSetPassword,
    'album-delete-btn': onDelete,
}

document.addEventListener('click', function (event) {
    for (const [cls, handler] of Object.entries(HANDLERS)) {
        const btn = event.target.closest(`.${cls}`)
        if (btn) {
            handler(btn)
            return
        }
    }
})

// Optimistic toggle for "Make Private/Public" — the album-update WS broadcast
// will reconcile, but flip the icon/label immediately so the menu feels live.
socket?.addEventListener('message', function (event) {
    if (event.data === 'pong') return
    let data
    try {
        data = JSON.parse(event.data)
    } catch {
        return
    }
    if (data.event === 'album-update' && data.id != null) {
        syncPrivateButtons(data.id, !!data.private)
        if (Object.prototype.hasOwnProperty.call(data, 'password')) {
            syncPasswordButtons(data.id, !!data.password)
        }
    }
})

function syncPrivateButtons(id, isPrivate) {
    const sel = `.album-toggle-private-btn[data-album-id="${CSS.escape(String(id))}"]`
    document.querySelectorAll(sel).forEach((btn) => {
        btn.dataset.private = isPrivate ? 'true' : 'false'
        const icon = btn.querySelector('i')
        if (icon) {
            icon.className = `fa-solid fa-${isPrivate ? 'globe' : 'lock'} fa-fw me-2`
        }
        const label = isPrivate ? 'Make Public' : 'Make Private'
        const textNode = [...btn.childNodes].find(
            (n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim()
        )
        if (textNode) textNode.textContent = label
        else btn.append(label)
    })
}

function syncPasswordButtons(id, hasPassword) {
    const sel = `.album-set-password-btn[data-album-id="${CSS.escape(String(id))}"]`
    document.querySelectorAll(sel).forEach((btn) => {
        btn.dataset.hasPassword = hasPassword ? 'true' : 'false'
        const textNode = [...btn.childNodes].find(
            (n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim()
        )
        if (textNode)
            textNode.textContent = hasPassword
                ? 'Change Password'
                : 'Set Password'
    })
}
