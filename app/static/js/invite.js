// JS for Invites

// Reveal the password / confirm-password fields only when requested.
$('#use-password').on('click', function () {
    $('#password-fields').removeClass('d-none')
    $(this).addClass('d-none')
    $('#password').trigger('focus')
})

function setFieldError(name, message) {
    $(`#${name}`).addClass('is-invalid')
    $(`#${name}-invalid`).text(message)
}

function clearPasswordErrors() {
    $('#password, #confirm_password').removeClass('is-invalid')
    $('#password-invalid, #confirm_password-invalid').empty()
}

// Live confirmation that the two password fields match (shared with the user
// settings password change). Only relevant to the local-password path; the
// passkey button never submits this form, so it is unaffected.
setupPasswordMatch(
    document.getElementById('password'),
    document.getElementById('confirm_password'),
    document.getElementById('confirm_password-invalid')
)

$('#inviteForm').on('submit', function (event) {
    console.log('#inviteForm submit', event)
    event.preventDefault()
    const form = $(this)
    console.log('form:', form)

    clearPasswordErrors()
    const password = $('#password').val()
    const confirm = $('#confirm_password').val()
    if (!password) {
        return setFieldError('password', 'Password is required.')
    }
    if (password.length < 6) {
        return setFieldError(
            'password',
            'Password must be at least 6 characters.'
        )
    }
    if (password !== confirm) {
        return setFieldError('confirm_password', 'Passwords do not match.')
    }

    $.ajax({
        type: form.attr('method'),
        url: form.attr('action'),
        data: new FormData(this),
        success: function (data) {
            console.log('data:', data)
            location.reload()
        },
        error: function (jqXHR) {
            formErrorHandler.call(this, form, jqXHR)
        },
        cache: false,
        contentType: false,
        processData: false,
    })
})

$('#inviteSearch').on('submit', function (event) {
    console.log('#inviteSearch submit', event)
    event.preventDefault()
    const invite = $(this)[0].invite.value.trim()
    console.log('invite:', invite)
    const action = $(this).attr('action')
    return window.location.replace(action + invite)
})
