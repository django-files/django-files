// Shared live password-match validation.
// Wires `input` listeners on a password / confirm-password pair so the confirm
// field shows an inline error until the two values match. Used by the invite
// signup and the user-settings password change. Returns the checker so callers
// can invoke it manually if needed.
// eslint-disable-next-line no-unused-vars
function setupPasswordMatch(
    passwordEl,
    confirmEl,
    feedbackEl,
    message = 'Passwords do not match.'
) {
    if (!passwordEl || !confirmEl) return null

    function checkPasswordMatch() {
        if (!confirmEl.value || confirmEl.value === passwordEl.value) {
            confirmEl.classList.remove('is-invalid')
            if (feedbackEl) feedbackEl.textContent = ''
        } else {
            confirmEl.classList.add('is-invalid')
            if (feedbackEl) feedbackEl.textContent = message
        }
    }

    passwordEl.addEventListener('input', checkPasswordMatch)
    confirmEl.addEventListener('input', checkPasswordMatch)
    return checkPasswordMatch
}
