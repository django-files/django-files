// Passkey (WebAuthn) account creation on the invite page.
import { setupPasskeyRegistration } from './passkey-register.js'

const form = document.getElementById('inviteForm')
const invite = form ? form.dataset.invite : ''

setupPasskeyRegistration({
    beginUrl: () => `/oauth/passkey/invite/${invite}/begin`,
    completeUrl: () => `/oauth/passkey/invite/${invite}/complete`,
    getDetails: (username) => ({ username }),
    defaultError: 'Could not create account.',
})
