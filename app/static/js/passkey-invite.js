// Passkey (WebAuthn) account creation on the invite page.
import {
    passkeysSupported,
    prepareCreation,
    serializeRegistration,
} from './webauthn.js'

const button = document.getElementById('passkey-create')
const form = document.getElementById('inviteForm')
const usernameInput = document.getElementById('username')
const feedback = document.getElementById('passkeyFeedback')

function showError(message) {
    if (!feedback) return
    feedback.textContent = message
    feedback.classList.remove('d-none')
    feedback.style.display = 'block'
}

function clearError() {
    if (!feedback) return
    feedback.classList.add('d-none')
    feedback.style.display = ''
}

async function postJSON(url, body) {
    const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : '{}',
    })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) {
        throw new Error(data.error || 'Could not create account.')
    }
    return data
}

async function createWithPasskey() {
    clearError()
    if (!passkeysSupported()) {
        showError('Passkeys are not supported in this browser.')
        return
    }
    const username = usernameInput ? usernameInput.value.trim() : ''
    if (!username) {
        showError('Please enter a username.')
        usernameInput?.focus()
        return
    }
    const invite = form.dataset.invite
    button.classList.add('disabled')
    try {
        const options = await postJSON(
            `/oauth/passkey/invite/${invite}/begin`,
            { username }
        )
        const credential = await navigator.credentials.create({
            publicKey: prepareCreation(options),
        })
        const payload = serializeRegistration(credential)
        const data = await postJSON(
            `/oauth/passkey/invite/${invite}/complete`,
            payload
        )
        if (data.redirect) {
            window.location.replace(data.redirect)
        } else {
            window.location.reload()
        }
    } catch (error) {
        console.error('passkey invite error:', error)
        // NotAllowedError = user cancelled / timed out; stay quiet about that.
        if (error.name !== 'NotAllowedError') {
            showError(error.message || 'Could not create account.')
        }
    } finally {
        button.classList.remove('disabled')
    }
}

if (button) {
    button.addEventListener('click', createWithPasskey)
}
