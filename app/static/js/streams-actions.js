// Shared click delegation for stream context-menu actions. Used by both the
// streams table (rendered per-row in streams-table.js) and the live view
// (rendered server-side in streams/ctx-menu.html). Items are identified by
// class + data attributes so both sources stay logic-free.

import { socket } from './socket.js'
import { wireDeleteModal } from './bulk-actions.js'
import {
    flashCopiedIcon,
    openPasswordModal,
    setMenuLabel,
    wireClickDelegation,
    wirePasswordModal,
} from './ctx-menu-shared.js'

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

async function copyRawLinkToClipboard(btn, url) {
    try {
        await navigator.clipboard.writeText(url)
        flashCopiedIcon(btn)
        if (typeof show_toast === 'function')
            show_toast('Raw link copied to clipboard.', 'info', '3000')
        return true
    } catch {
        if (typeof show_toast === 'function')
            show_toast('Failed to copy raw link.', 'danger', '4000')
        return false
    }
}

async function fetchOwnerVlcUrl(name) {
    const res = await fetch(`/api/stream/${encodeURIComponent(name)}/vlc-url/`)
    if (!res.ok) {
        if (typeof show_toast === 'function')
            show_toast('Failed to fetch raw link.', 'danger', '4000')
        return null
    }
    const { url } = await res.json()
    return url || null
}

async function copyVlcUrlForStream(btn, name) {
    // Non-owner viewers get the URL baked into data-static-url server-side (the
    // viewer already passed the access gate when live_view rendered the page).
    // Owners hit the API instead so a freshly-rotated token is reflected without
    // a reload.
    const staticUrl = btn.dataset.staticUrl
    if (staticUrl) return copyRawLinkToClipboard(btn, staticUrl)
    const url = await fetchOwnerVlcUrl(name)
    if (!url) return false
    return copyRawLinkToClipboard(btn, url)
}

async function onCopyVlcUrl(btn) {
    const name = btn.dataset.streamName
    if (!name) return
    const enabled = btn.dataset.enabled === 'true'
    if (enabled) {
        await copyVlcUrlForStream(btn, name)
        return
    }
    // Disabled → enable (mint a fresh token), then copy.
    try {
        const res = await fetch(
            `/api/stream/${encodeURIComponent(name)}/enable-playback-token/`,
            { method: 'POST', headers: { 'X-CSRFToken': csrfToken() } }
        )
        if (!res.ok) {
            if (typeof show_toast === 'function')
                show_toast('Failed to enable raw link.', 'danger', '4000')
            return
        }
        const { url } = await res.json()
        if (url) {
            await navigator.clipboard.writeText(url)
            if (typeof show_toast === 'function')
                show_toast('Raw link enabled and copied.', 'success', '4000')
        }
        syncVlcButtons(name, true)
    } catch {
        if (typeof show_toast === 'function')
            show_toast('Failed to enable raw link.', 'danger', '4000')
    }
}

async function onDisableVlcUrl(btn) {
    const name = btn.dataset.streamName
    if (!name) return
    try {
        const res = await fetch(
            `/api/stream/${encodeURIComponent(name)}/disable-playback-token/`,
            { method: 'POST', headers: { 'X-CSRFToken': csrfToken() } }
        )
        if (!res.ok) {
            if (typeof show_toast === 'function')
                show_toast('Failed to disable raw link.', 'danger', '4000')
            return
        }
        syncVlcButtons(name, false)
        if (typeof show_toast === 'function')
            show_toast('Raw link disabled.', 'info', '3000')
    } catch {
        if (typeof show_toast === 'function')
            show_toast('Failed to disable raw link.', 'danger', '4000')
    }
}

function syncVlcButtons(name, enabled) {
    const copySel = `.stream-copy-vlc-url-btn[data-stream-name="${CSS.escape(name)}"]`
    document.querySelectorAll(copySel).forEach((btn) => {
        btn.dataset.enabled = enabled ? 'true' : 'false'
        const icon = btn.querySelector('i')
        if (icon) {
            icon.className = `fa-solid fa-${enabled ? 'link' : 'link-slash'} fa-fw me-2 link-info`
        }
        setMenuLabel(btn, enabled ? 'Copy Raw Link' : 'Enable Raw Link')
    })
    // The "Disable Raw Link" wrapper <li> is always rendered; show/hide it so a
    // newly-enabled stream gets the action without needing a re-render.
    const disableSel = `.stream-disable-vlc-url-item[data-stream-name="${CSS.escape(name)}"]`
    document.querySelectorAll(disableSel).forEach((li) => {
        li.classList.toggle('d-none', !enabled)
    })
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

function onSetPassword(btn) {
    const name = btn.dataset.streamName
    if (!name) return
    openPasswordModal({
        modalId: 'streamPasswordModal',
        keyField: 'name',
        keyValue: name,
        currentValueSelector: 'input[name=current-stream-password]',
        btn,
    })
}

wirePasswordModal({
    modalId: 'streamPasswordModal',
    formId: 'modal-stream-password-form',
    inputId: 'stream-password-input',
    unmaskId: 'stream-password-unmask',
    copyId: 'stream-password-copy',
    generateId: 'stream-password-generate',
    keyField: 'name',
    method: 'set_stream_password',
    onSubmitted: ({ key, password }) => {
        const name = String(key)
        document
            .querySelectorAll(
                `.stream-ctx-menu[data-stream-name="${CSS.escape(name)}"] input[name=current-stream-password]`
            )
            .forEach((el) => {
                el.value = password
            })
        document
            .querySelectorAll(
                `.stream-set-password-btn[data-stream-name="${CSS.escape(name)}"]`
            )
            .forEach((el) => {
                el.dataset.hasPassword = password ? 'true' : 'false'
                setMenuLabel(el, password ? 'Change Password' : 'Set Password')
            })
    },
})

wireClickDelegation({
    'stream-copy-rtmp-btn': onCopyRtmp,
    'stream-rotate-token-btn': onRotateToken,
    'stream-copy-vlc-url-btn': onCopyVlcUrl,
    'stream-disable-vlc-url-btn': onDisableVlcUrl,
    'stream-toggle-public-btn': onTogglePublic,
    'stream-set-password-btn': onSetPassword,
    'stream-delete-btn': onDelete,
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
        setMenuLabel(btn, isPublic ? 'Make Private' : 'Make Public')
    })
}
