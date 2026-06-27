// Shared WebAuthn / passkey helpers.
// Converts between the base64url JSON emitted by py_webauthn (server side)
// and the ArrayBuffer-based structures the browser credential APIs expect.

export function bufferToBase64url(buffer) {
    const bytes = new Uint8Array(buffer)
    let str = ''
    for (const byte of bytes) {
        str += String.fromCodePoint(byte)
    }
    return btoa(str)
        .replaceAll('+', '-')
        .replaceAll('/', '_')
        .replaceAll('=', '')
}

export function base64urlToBuffer(value) {
    const padded = value.replaceAll('-', '+').replaceAll('_', '/')
    const padLen = (4 - (padded.length % 4)) % 4
    const binary = atob(padded + '='.repeat(padLen))
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.codePointAt(i)
    }
    return bytes.buffer
}

// Convert server registration options (JSON) into PublicKeyCredentialCreationOptions.
export function prepareCreation(options) {
    options.challenge = base64urlToBuffer(options.challenge)
    options.user.id = base64urlToBuffer(options.user.id)
    if (options.excludeCredentials) {
        options.excludeCredentials = options.excludeCredentials.map((cred) => ({
            ...cred,
            id: base64urlToBuffer(cred.id),
        }))
    }
    return options
}

// Serialize a freshly created credential (attestation) back to base64url JSON.
export function serializeRegistration(credential) {
    const response = credential.response
    const transports =
        typeof response.getTransports === 'function'
            ? response.getTransports()
            : []
    return {
        id: credential.id,
        rawId: bufferToBase64url(credential.rawId),
        type: credential.type,
        authenticatorAttachment: credential.authenticatorAttachment,
        response: {
            clientDataJSON: bufferToBase64url(response.clientDataJSON),
            attestationObject: bufferToBase64url(response.attestationObject),
            transports,
        },
    }
}

// Convert server authentication options (JSON) into PublicKeyCredentialRequestOptions.
export function prepareRequest(options) {
    options.challenge = base64urlToBuffer(options.challenge)
    if (options.allowCredentials) {
        options.allowCredentials = options.allowCredentials.map((cred) => ({
            ...cred,
            id: base64urlToBuffer(cred.id),
        }))
    }
    return options
}

// Serialize an assertion back to base64url JSON for verification.
export function serializeAuthentication(credential) {
    const response = credential.response
    return {
        id: credential.id,
        rawId: bufferToBase64url(credential.rawId),
        type: credential.type,
        authenticatorAttachment: credential.authenticatorAttachment,
        response: {
            clientDataJSON: bufferToBase64url(response.clientDataJSON),
            authenticatorData: bufferToBase64url(response.authenticatorData),
            signature: bufferToBase64url(response.signature),
            userHandle: response.userHandle
                ? bufferToBase64url(response.userHandle)
                : null,
        },
    }
}

export function passkeysSupported() {
    return (
        window.PublicKeyCredential !== undefined &&
        navigator.credentials !== undefined
    )
}
