// Shared passkey (WebAuthn) account-creation ceremony.
// Used by both the invite page and the first-run setup page: wires the
// #passkey-create button to register a new credential and redirect on success.
import {
    passkeysSupported,
    prepareCreation,
    serializeRegistration,
} from './webauthn.js'

export function setupPasskeyRegistration({
    beginUrl,
    completeUrl,
    getDetails,
    defaultError = 'Could not complete registration.',
}) {
    const button = document.getElementById('passkey-create')
    if (!button) return
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
            throw new Error(data.error || defaultError)
        }
        return data
    }

    async function register() {
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
        button.classList.add('disabled')
        try {
            const options = await postJSON(beginUrl(), getDetails(username))
            const credential = await navigator.credentials.create({
                publicKey: prepareCreation(options),
            })
            const data = await postJSON(
                completeUrl(),
                serializeRegistration(credential)
            )
            if (data.redirect) {
                window.location.replace(data.redirect)
            } else {
                window.location.reload()
            }
        } catch (error) {
            console.error('passkey registration error:', error)
            // NotAllowedError = user cancelled / timed out; stay quiet about that.
            if (error.name !== 'NotAllowedError') {
                showError(error.message || defaultError)
            }
        } finally {
            button.classList.remove('disabled')
        }
    }

    if (passkeysSupported()) {
        button.addEventListener('click', register)
    } else {
        button.classList.add('d-none')
    }
}
