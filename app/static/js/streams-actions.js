// Shared click delegation for stream context-menu actions. Used by both the
// streams table (rendered per-row in streams-table.js) and the live view
// (rendered server-side in streams/ctx-menu.html). Items are identified by
// class + data attributes so both sources stay logic-free.

import { socket } from './socket.js'
import { wireDeleteModal } from './bulk-actions.js'

const csrfToken = () => /csrftoken=([^;]+)/.exec(document.cookie)?.[1] || ''

let _deleteModal
let pendingRedirect = null

function ensureDeleteModal() {
    if (_deleteModal !== undefined) return _deleteModal
    _deleteModal = document.getElementById('delete-stream-modal')
        ? wireDeleteModal({
              modalId: 'delete-stream-modal',
              bodyId: 'delete-stream-body',
              confirmId: 'stream-delete-confirm',
              entity: 'stream',
              onConfirm: (ids) => {
                  socket.send(
                      JSON.stringify({ method: 'delete-streams', pks: ids })
                  )
              },
          })
        : null
    return _deleteModal
}

let _rotateConfirmResolver = null

// Expose for the stream-setup modal's inline (non-module) script.
window.confirmRotateStreamToken = (name) => confirmRotateToken(name)

function confirmRotateToken(name) {
    const modalEl = document.getElementById('regenerate-token-modal')
    if (!modalEl) {
        return Promise.resolve(
            confirm(
                `Rotate the stream token for "${name}"? The current RTMP URL will stop working until updated.`
            )
        )
    }
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl)
    const body = document.getElementById('regenerate-token-body')
    if (body) {
        body.textContent = `Rotate the stream token for "${name}"? The current RTMP URL will stop working until updated in your streaming client.`
    }
    return new Promise((resolve) => {
        _rotateConfirmResolver = resolve
        modal.show()
    })
}

document
    .getElementById('regenerate-token-confirm')
    ?.addEventListener('click', function () {
        const modalEl = document.getElementById('regenerate-token-modal')
        const modal = modalEl
            ? bootstrap.Modal.getOrCreateInstance(modalEl)
            : null
        const resolve = _rotateConfirmResolver
        _rotateConfirmResolver = null
        modal?.hide()
        resolve?.(true)
    })

document
    .getElementById('regenerate-token-modal')
    ?.addEventListener('hidden.bs.modal', function () {
        const resolve = _rotateConfirmResolver
        _rotateConfirmResolver = null
        resolve?.(false)
    })

export function openDeleteStreamsModal(names) {
    const modal = ensureDeleteModal()
    if (modal) modal.open(names)
    else if (names.length && confirm(`Delete ${names.length} stream(s)?`)) {
        socket.send(JSON.stringify({ method: 'delete-streams', pks: names }))
    }
}

async function onCopyRtmp(btn) {
    const url = btn.dataset.rtmpUrl
    if (!url) return
    await navigator.clipboard.writeText(url)
    const icon = btn.querySelector('i')
    if (!icon) return
    const orig = icon.className
    icon.className = 'fa-solid fa-check fa-fw me-2'
    setTimeout(() => {
        icon.className = orig
    }, 2000)
    if (typeof show_toast === 'function') {
        show_toast('RTMP URL copied to clipboard.', 'info', '3000')
    }
}

async function onRotateToken(btn) {
    const name = btn.dataset.streamName
    if (!name) return
    const confirmed = await confirmRotateToken(name)
    if (!confirmed) return
    try {
        const res = await fetch(
            `/api/stream/${encodeURIComponent(name)}/rotate-token/`,
            {
                method: 'POST',
                headers: { 'X-CSRFToken': csrfToken() },
            }
        )
        if (!res.ok) {
            if (typeof show_toast === 'function')
                show_toast('Failed to rotate token.', 'danger', '4000')
            return
        }
        const { stream_token: newToken } = await res.json()
        if (newToken) {
            updateRtmpToken(name, newToken)
            document.dispatchEvent(
                new CustomEvent('stream-token-rotated', {
                    detail: { name, token: newToken },
                })
            )
        }
        if (typeof show_toast === 'function')
            show_toast(
                'Token rotated. Copy the new RTMP URL.',
                'success',
                '4000'
            )
    } catch {
        if (typeof show_toast === 'function')
            show_toast('Failed to rotate token.', 'danger', '4000')
    }
}

function onTogglePublic(btn) {
    const name = btn.dataset.streamName
    if (!name) return
    const makePublic =
        btn.dataset.public === 'false' || btn.dataset.public === false
    socket.send(
        JSON.stringify({
            method: 'private_streams',
            pks: [name],
            public: makePublic,
        })
    )
}

function onDelete(btn) {
    const name = btn.dataset.hookId
    if (!name) return
    const redirect = btn.dataset.redirectOnDelete
    if (redirect) pendingRedirect = { name, url: redirect }
    openDeleteStreamsModal([name])
}

const HANDLERS = {
    'stream-copy-rtmp-btn': onCopyRtmp,
    'stream-rotate-token-btn': onRotateToken,
    'stream-toggle-public-btn': onTogglePublic,
    'stream-delete-btn': onDelete,
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

// When the live view triggers a delete, redirect once the websocket confirms it.
socket?.addEventListener('message', function (event) {
    if (event.data === 'pong') return
    let data
    try {
        data = JSON.parse(event.data)
    } catch {
        return
    }
    if (data.event === 'stream-delete' && pendingRedirect?.name === data.name) {
        const url = pendingRedirect.url
        pendingRedirect = null
        window.location.href = url
    } else if (data.event === 'toggle-public-stream') {
        data.objects.forEach((obj) => {
            syncPublicToggleButtons(obj.name, obj.public)
            syncPublicBadge(obj.name, obj.public)
        })
    }
})

document.addEventListener('stream-token-rotated', function (e) {
    if (e.detail?.name && e.detail?.token) {
        updateRtmpToken(e.detail.name, e.detail.token)
    }
})

function updateRtmpToken(name, newToken) {
    const selector = `.stream-copy-rtmp-btn[data-stream-name="${CSS.escape(name)}"]`
    document.querySelectorAll(selector).forEach((btn) => {
        const current = btn.dataset.rtmpUrl
        if (!current) return
        btn.dataset.rtmpUrl = current.replace(
            /(stream_token=)[^&]*/,
            `$1${encodeURIComponent(newToken)}`
        )
    })
}

function syncPublicBadge(name, isPublic) {
    const selector = `#stream-public-badge[data-stream-name="${CSS.escape(name)}"]`
    document.querySelectorAll(selector).forEach((el) => {
        el.classList.toggle('d-none', isPublic)
    })
}

function syncPublicToggleButtons(name, isPublic) {
    const selector = `.stream-toggle-public-btn[data-stream-name="${CSS.escape(name)}"]`
    document.querySelectorAll(selector).forEach((btn) => {
        btn.dataset.public = isPublic ? 'true' : 'false'
        const icon = btn.querySelector('i')
        if (icon) {
            icon.className = `fa-solid fa-${isPublic ? 'lock' : 'globe'} fa-fw me-2`
        }
        const label = isPublic ? 'Make Private' : 'Make Public'
        const textNode = [...btn.childNodes].find(
            (n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim()
        )
        if (textNode) textNode.textContent = label
        else btn.append(label)
    })
}
