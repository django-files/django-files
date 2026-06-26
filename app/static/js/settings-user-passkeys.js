// Passkey (WebAuthn) management on the user settings page.
import {
    passkeysSupported,
    prepareCreation,
    serializeRegistration,
} from './webauthn.js'

const listEl = document.getElementById('passkey-list')
const addBtn = document.getElementById('addPasskeyBtn')
const errorEl = document.getElementById('passkey-error')
const modalEl = document.getElementById('modal-new-passkey')
const formEl = document.getElementById('new-passkey-form')
const nameInput = document.getElementById('passkey-name')
const confirmBtn = document.getElementById('confirm-new-passkey-btn')
const modalErrorEl = document.getElementById('new-passkey-error')

function csrf() {
    const el = document.querySelector('input[name="csrfmiddlewaretoken"]')
    return el ? el.value : ''
}

function showError(message) {
    if (!errorEl) return
    errorEl.textContent = message
    errorEl.classList.remove('d-none')
}

function clearError() {
    if (errorEl) errorEl.classList.add('d-none')
}

function showModalError(message) {
    if (!modalErrorEl) return
    modalErrorEl.textContent = message
    modalErrorEl.classList.remove('d-none')
}

function clearModalError() {
    if (modalErrorEl) modalErrorEl.classList.add('d-none')
}

async function postJSON(url, body) {
    const resp = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrf(),
        },
        body: body ? JSON.stringify(body) : '{}',
    })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) {
        throw new Error(data.error || 'Request failed.')
    }
    return data
}

function fmtDate(iso) {
    if (!iso) return 'never'
    return new Date(iso).toLocaleString()
}

function renderList(passkeys) {
    listEl.innerHTML = ''
    if (!passkeys.length) {
        const li = document.createElement('li')
        li.className = 'list-group-item text-muted small'
        li.textContent = 'No passkeys registered.'
        listEl.appendChild(li)
        return
    }
    for (const pk of passkeys) {
        const li = document.createElement('li')
        li.className =
            'list-group-item d-flex align-items-center justify-content-between gap-2'

        const info = document.createElement('div')
        const name = document.createElement('div')
        name.className = 'fw-medium'
        name.textContent = pk.name || 'Passkey'
        const meta = document.createElement('div')
        meta.className = 'text-muted small'
        meta.textContent = `Added ${fmtDate(pk.created_at)} · Last used ${fmtDate(pk.last_used_at)}`
        info.append(name, meta)

        const del = document.createElement('button')
        del.type = 'button'
        del.className = 'btn btn-sm btn-outline-danger flex-shrink-0'
        del.innerHTML = '<i class="fa-solid fa-trash"></i>'
        del.addEventListener('click', () => removePasskey(pk.id, pk.name))

        li.append(info, del)
        listEl.appendChild(li)
    }
}

async function loadList() {
    try {
        const data = await postGet('/oauth/passkey/list')
        renderList(data.passkeys || [])
    } catch (error) {
        console.error('passkey list error:', error)
        showError('Could not load passkeys.')
    }
}

async function postGet(url) {
    const resp = await fetch(url, { headers: { 'X-CSRFToken': csrf() } })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(data.error || 'Request failed.')
    return data
}

async function addPasskey(event) {
    event.preventDefault()
    clearModalError()
    if (!passkeysSupported()) {
        showModalError('Passkeys are not supported in this browser.')
        return
    }
    confirmBtn.classList.add('disabled')
    try {
        const options = await postJSON('/oauth/passkey/register/begin')
        const credential = await navigator.credentials.create({
            publicKey: prepareCreation(options),
        })
        const payload = serializeRegistration(credential)
        payload.name = nameInput ? nameInput.value.trim() : ''
        await postJSON('/oauth/passkey/register/complete', payload)
        bootstrap.Modal.getInstance(modalEl)?.hide()
        await loadList()
    } catch (error) {
        console.error('passkey register error:', error)
        // NotAllowedError = user cancelled / timed out; leave the modal open quietly.
        if (error.name !== 'NotAllowedError') {
            showModalError(error.message || 'Could not register passkey.')
        }
    } finally {
        confirmBtn.classList.remove('disabled')
    }
}

async function removePasskey(id, name) {
    if (!window.confirm(`Remove passkey "${name || 'Passkey'}"?`)) return
    clearError()
    try {
        await postJSON(`/oauth/passkey/${id}/delete`)
        await loadList()
    } catch (error) {
        console.error('passkey delete error:', error)
        showError('Could not remove passkey.')
    }
}

if (addBtn) {
    loadList()
}

if (formEl) {
    formEl.addEventListener('submit', addPasskey)
}

// Reset the name field and any error each time the modal opens.
if (modalEl) {
    modalEl.addEventListener('show.bs.modal', () => {
        clearModalError()
        if (nameInput) nameInput.value = ''
    })
}
