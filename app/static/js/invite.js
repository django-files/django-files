// JS for Invites

$('#inviteForm').on('submit', function (event) {
    console.log('#inviteForm.submit', event)
    event.preventDefault()
    const form = $(this)
    $.ajax({
        url: form.attr('action'),
        type: form.attr('method'),
        data: new FormData(this),
        success: function (data) {
            console.log('data:', data)
            location.reload()
        },
        error: function (jqXHR) {
            if (jqXHR.status === 400) {
                form400handler.call(this, form, jqXHR)
            }
            const message = `${jqXHR.status}: ${jqXHR.statusText}`
            show_toast(message, 'danger', '6000')
        },
        cache: false,
        contentType: false,
        processData: false,
    })
})

// Handle invite code searches
$('#inviteSearch').on('submit', function (event) {
    console.log('#inviteSearch.submit', event)
    event.preventDefault()
    const invite = $(this)[0].invite.value.trim()
    console.log('invite:', invite)
    const action = $(this).attr('action')
    return window.location.replace(action + invite)
})
