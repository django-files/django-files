// JS for the first-run setup page.
// Reveals the password fields only when the user opts for a password instead of
// a passkey, and wires live password-match feedback.

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
