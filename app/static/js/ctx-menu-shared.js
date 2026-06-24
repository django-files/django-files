// Shared helpers for the per-resource context menus (streams, albums, etc.).
// Pulled out so streams-actions.js and albums-actions.js — which had nearly
// identical password-modal wiring and clipboard feedback — share a single
// implementation. New ctx-menu modules should consume from here too.

import { socket } from './socket.js'

export function flashCopiedIcon(btn) {
    const icon = btn.querySelector('i')
    if (!icon) return
    const orig = icon.className
    icon.className = 'fa-solid fa-check fa-fw me-2'
    setTimeout(() => {
        icon.className = orig
    }, 2000)
}

// Replace the leading text node of `btn` with `label`, falling back to append
// if no text node exists yet. Preserves icon children + dataset attributes.
export function setMenuLabel(btn, label) {
    const textNode = [...btn.childNodes].find(
        (n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim()
    )
    if (textNode) textNode.textContent = label
    else btn.append(label)
}

// Wire a "set password" modal: the form submit dispatches a WS method, and the
// three input-group buttons (unmask / copy / generate) get standard behavior.
//
// config: {
//   modalId, formId, inputId, unmaskId, copyId, generateId,
//   keyField,        // hidden input name in the form carrying the resource id
//   castKey,         // optional: transform key string before sending (e.g. parseInt)
//   method,          // WS method name (e.g. 'set_stream_password')
//   onSubmitted,     // optional: called with ({ key, password }) after socket.send
//                    // so callers can do optimistic in-DOM sync (label flip etc.)
// }
export function wirePasswordModal(config) {
    const {
        modalId,
        formId,
        inputId,
        unmaskId,
        copyId,
        generateId,
        keyField,
        castKey,
        method,
        onSubmitted,
    } = config

    document
        .getElementById(formId)
        ?.addEventListener('submit', function (event) {
            event.preventDefault()
            const form = event.currentTarget
            const rawKey = form.elements[keyField]?.value
            const key = castKey ? castKey(rawKey) : rawKey
            const password = form.elements.password.value
            if (!key) return
            const payload = { method, password }
            payload[keyField] = key
            socket.send(JSON.stringify(payload))
            onSubmitted?.({ key, password })
            const modalEl = document.getElementById(modalId)
            if (modalEl) bootstrap.Modal.getOrCreateInstance(modalEl).hide()
        })

    document.getElementById(unmaskId)?.addEventListener('click', function () {
        const input = document.getElementById(inputId)
        if (!input) return
        input.type = input.type === 'password' ? 'text' : 'password'
    })

    document
        .getElementById(copyId)
        ?.addEventListener('click', async function () {
            const input = document.getElementById(inputId)
            if (!input?.value) return
            try {
                await navigator.clipboard.writeText(input.value)
                if (typeof show_toast === 'function')
                    show_toast('Password copied to clipboard.', 'info', '3000')
            } catch {
                /* clipboard denied */
            }
        })

    document.getElementById(generateId)?.addEventListener('click', function () {
        const input = document.getElementById(inputId)
        if (!input) return
        const bytes = new Uint8Array(12)
        crypto.getRandomValues(bytes)
        input.value = btoa(String.fromCodePoint(...bytes))
            .replace(/[+/=]/g, '')
            .slice(0, 16)
        input.type = 'text'
    })
}

// Open a "set password" modal pre-filled with the current value scraped from
// a sibling hidden input on the ctx-menu wrapper. The btn's closest container
// is configurable via `wrapperSelector` because file ctx menus use `.ctx-menu`
// while stream/album use the stock bootstrap `.dropdown` wrapper.
export function openPasswordModal({
    modalId,
    keyField,
    keyValue,
    currentValueSelector,
    wrapperSelector = '.dropdown',
    btn,
}) {
    const modalEl = document.getElementById(modalId)
    if (!modalEl) return
    const current =
        btn.closest(wrapperSelector)?.querySelector(currentValueSelector)
            ?.value || ''
    modalEl.querySelector(`input[name=${keyField}]`).value = keyValue
    const input = modalEl.querySelector('input[name=password]')
    input.value = current
    input.type = 'text'
    // Focus + select on open so the user can immediately type, paste, or clear.
    // One-shot listener prevents accumulation across repeated opens.
    modalEl.addEventListener(
        'shown.bs.modal',
        function autofocus() {
            input.focus()
            input.select()
        },
        { once: true }
    )
    bootstrap.Modal.getOrCreateInstance(modalEl).show()
}

// Run handlers off a single document click listener, keyed by class.
export function wireClickDelegation(handlers) {
    document.addEventListener('click', function (event) {
        for (const [cls, handler] of Object.entries(handlers)) {
            const btn = event.target.closest(`.${cls}`)
            if (btn) {
                handler(btn)
                return
            }
        }
    })
}
