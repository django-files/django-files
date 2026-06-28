// JS for the first-run setup page.
// Reveals the password fields only when the user opts for a password instead of
// a passkey, and wires live password-match feedback.

// Prefill Site URL from the browser origin (which carries the real port) when
// the server hasn't already set one. The server may sit behind a proxy that
// hides the port, so it cannot derive this itself.
const siteUrlField = document.getElementById('site_url')
if (siteUrlField && !siteUrlField.value) {
    siteUrlField.value = window.location.origin
}

// Detect and prefill the client's timezone (the server cannot know it).
const timezoneField = document.getElementById('timezone')
const detectedTimezone = new window.Intl.DateTimeFormat().resolvedOptions()
    .timeZone
if (timezoneField && detectedTimezone) {
    timezoneField.value = detectedTimezone
}

$('#use-password').on('click', function () {
    $('#password-fields').removeClass('d-none')
    $(this).addClass('d-none')
    $('#password').trigger('focus')
})

setupPasswordMatch(
    document.getElementById('password'),
    document.getElementById('confirm_password'),
    document.getElementById('confirm_password-invalid')
)
