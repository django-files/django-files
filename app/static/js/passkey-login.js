// Passkey (WebAuthn) login flow for the login page.
import {
    passkeysSupported,
    prepareRequest,
    serializeAuthentication,
} from './webauthn.js'

const button = document.getElementById('passkey-login')
const feedback = document.getElementById('passkeyFeedback')
const loginOuter = document.getElementById('login-outer')

function showError(message) {
    if (!feedback) return
    feedback.textContent = message
    feedback.classList.remove('d-none')
    feedback.style.display = 'block'
}

async function postJSON(url, body) {
    const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : '{}',
    })
    const data = await resp.json().catch(() => ({}))
    if (!resp.ok) {
        throw new Error(data.error || 'Passkey authentication failed.')
    }
    return data
}

async function authenticate() {
    if (!passkeysSupported()) {
        showError('Passkeys are not supported in this browser.')
        return
    }
    button.classList.add('disabled')
    try {
        const options = await postJSON('/oauth/passkey/auth/begin')
        const assertion = await navigator.credentials.get({
            publicKey: prepareRequest(options),
        })
        const data = await postJSON(
            '/oauth/passkey/auth/complete',
            serializeAuthentication(assertion)
        )
        if (loginOuter) {
            loginOuter.classList.add(
                'animate__animated',
                'animate__backOutUp',
                'animate__slow'
            )
        }
        if (data.redirect) {
            window.location.replace(data.redirect)
        } else {
            window.location.reload()
        }
    } catch (error) {
        console.error('passkey login error:', error)
        // NotAllowedError = user cancelled / timed out; stay quiet about that.
        if (error.name !== 'NotAllowedError') {
            showError(error.message || 'Passkey authentication failed.')
        }
    } finally {
        button.classList.remove('disabled')
    }
}

if (button) {
    button.addEventListener('click', authenticate)
}

// Auto-start the ceremony when the page is opened via ?autopasskey=1 (e.g. a
// native client that deep-linked here specifically for passkey login).
// Requires a user gesture proxy: most browsers permit navigator.credentials.get
// without one if the navigation that opened the page was itself user-initiated,
// which is the case for the in-app web auth session.
if (button && new URLSearchParams(window.location.search).get('autopasskey') === '1') {
    authenticate()
}
