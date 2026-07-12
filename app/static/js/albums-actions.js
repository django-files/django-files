// Click delegation for album context-menu actions emitted by albums-table.js.
// Mirrors streams-actions.js so both surfaces stay consistent. Shared helpers
// (clipboard feedback, label flips, password-modal wiring, click delegation)
// live in ctx-menu-shared.js.

import { socket } from './socket.js'
import {
    flashCopiedIcon,
    openPasswordModal,
    setMenuLabel,
    wireClickDelegation,
    wirePasswordModal,
} from './ctx-menu-shared.js'
import { renderTagChips } from './tag-chips.js'

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
    openPasswordModal({
        modalId: 'albumPasswordModal',
        keyField: 'pk',
        keyValue: pk,
        currentValueSelector: 'input[name=current-album-password]',
        btn,
    })
}

wirePasswordModal({
    modalId: 'albumPasswordModal',
    formId: 'modal-album-password-form',
    inputId: 'album-password-input',
    unmaskId: 'album-password-unmask',
    copyId: 'album-password-copy',
    generateId: 'album-password-generate',
    keyField: 'pk',
    castKey: (v) => Number.parseInt(v),
    method: 'set_album_password',
    onSubmitted: ({ key, password }) => {
        const id = String(key)
        document
            .querySelectorAll(
                `.album-ctx-menu[data-album-id="${CSS.escape(id)}"] input[name=current-album-password]`
            )
            .forEach((el) => {
                el.value = password
            })
        syncPasswordButtons(id, !!password)
    },
})

// ── Album tags modal ──
// Chips render from local state seeded by the ctx-menu button's
// data-album-tags payload; set-album-tags broadcasts reconcile it live.

let tagsModalAlbumId = null
let tagsModalTags = []

function renderAlbumTagChips() {
    const container = document.getElementById('album-tags-container')
    if (!container) return
    // removal is confirmed by the set-album-tags broadcast, which re-renders
    renderTagChips(
        container,
        tagsModalTags,
        (tag) => {
            socket.send(
                JSON.stringify({
                    method: 'remove_album_tag',
                    pk: Number.parseInt(tagsModalAlbumId),
                    tag,
                })
            )
        },
        document.getElementById('album-tags-empty')
    )
}

function onManageTags(btn) {
    tagsModalAlbumId = btn.dataset.albumId
    try {
        tagsModalTags = JSON.parse(btn.dataset.albumTags || '[]')
    } catch {
        tagsModalTags = []
    }
    renderAlbumTagChips()
    const modalEl = document.getElementById('album-tags-modal')
    if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).show()
}

document
    .getElementById('album-tag-add-form')
    ?.addEventListener('submit', (event) => {
        event.preventDefault()
        const input = document.getElementById('album-tag-input')
        const tag = input.value.trim()
        if (!tag || !tagsModalAlbumId) return
        socket.send(
            JSON.stringify({
                method: 'add_album_tag',
                pk: Number.parseInt(tagsModalAlbumId),
                tag,
            })
        )
        input.value = ''
    })

function syncAlbumTagsState(data) {
    if (String(data.album_id) === String(tagsModalAlbumId)) {
        const tags = new Set(tagsModalTags)
        for (const tag of data.added || []) tags.add(tag)
        for (const tag of data.removed || []) tags.delete(tag)
        tagsModalTags = [...tags]
        renderAlbumTagChips()
    }
}

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

wireClickDelegation({
    'album-copy-link-btn': onCopyLink,
    'album-toggle-private-btn': onTogglePrivate,
    'album-set-password-btn': onSetPassword,
    'album-tags-btn': onManageTags,
    'album-delete-btn': onDelete,
})

// Optimistic reconciliation against the album-update WS broadcast — flips
// icons/labels on all rendered rows when the server confirms a change.
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
        if (Object.hasOwn(data, 'password')) {
            syncPasswordButtons(data.id, !!data.password)
        }
    }
    if (data.event === 'set-album-tags' && data.album_id != null) {
        syncAlbumTagsState(data)
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
        setMenuLabel(btn, isPrivate ? 'Make Public' : 'Make Private')
    })
}

function syncPasswordButtons(id, hasPassword) {
    const sel = `.album-set-password-btn[data-album-id="${CSS.escape(String(id))}"]`
    document.querySelectorAll(sel).forEach((btn) => {
        btn.dataset.hasPassword = hasPassword ? 'true' : 'false'
        setMenuLabel(btn, hasPassword ? 'Change Password' : 'Set Password')
    })
}
