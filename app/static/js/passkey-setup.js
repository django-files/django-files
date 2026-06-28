// Passkey (WebAuthn) creation of the initial admin on the first-run setup page.
import {
    passkeysSupported,
    prepareCreation,
    serializeRegistration,
} from './webauthn.js'

const button = document.getElementById('passkey-create')
const usernameInput = document.getElementById('username')
const timezoneInput = document.getElementById('timezone')
const siteUrlInput = document.getElementById('site_url')
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
        throw new Error(data.error || 'Could not complete setup.')
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
    const details = {
        username,
        timezone: timezoneInput ? timezoneInput.value.trim() : '',
        site_url: siteUrlInput ? siteUrlInput.value.trim() : '',
        // The browser origin carries the real port; the server may sit behind a
        // proxy that strips it, so it cannot derive the WebAuthn origin itself.
        origin: window.location.origin,
    }
    button.classList.add('disabled')
    try {
        const options = await postJSON('/oauth/passkey/setup/begin', details)
        const credential = await navigator.credentials.create({
            publicKey: prepareCreation(options),
        })
        const payload = serializeRegistration(credential)
        const data = await postJSON('/oauth/passkey/setup/complete', payload)
        if (data.redirect) {
            window.location.replace(data.redirect)
        } else {
            window.location.reload()
        }
    } catch (error) {
        console.error('passkey setup error:', error)
        // NotAllowedError = user cancelled / timed out; stay quiet about that.
        if (error.name !== 'NotAllowedError') {
            showError(error.message || 'Could not complete setup.')
        }
    } finally {
        button.classList.remove('disabled')
    }
}

if (button) {
    // Hide the passkey option entirely on clients without WebAuthn support.
    if (passkeysSupported()) {
        button.addEventListener('click', createWithPasskey)
    } else {
        button.classList.add('d-none')
    }
}
