// JS for Invites

$('#inviteForm').on('submit', function (event) {
    console.log('#inviteForm submit', event)
    event.preventDefault()
    const form = $(this)
    console.log('form:', form)
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
