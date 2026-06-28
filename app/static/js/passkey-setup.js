// Passkey (WebAuthn) creation of the initial admin on the first-run setup page.
import { setupPasskeyRegistration } from './passkey-register.js'

setupPasskeyRegistration({
    beginUrl: () => '/oauth/passkey/setup/begin',
    completeUrl: () => '/oauth/passkey/setup/complete',
    getDetails: (username) => ({
        username,
        timezone: document.getElementById('timezone')?.value.trim() || '',
        site_url: document.getElementById('site_url')?.value.trim() || '',
        // The browser origin carries the real port; the server may sit behind a
        // proxy that strips it, so it cannot derive the WebAuthn origin itself.
        origin: window.location.origin,
    }),
    defaultError: 'Could not complete setup.',
})
