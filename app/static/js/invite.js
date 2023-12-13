// JS for Invites

$('#inviteForm').on('submit', function (event) {
    event.preventDefault()
    console.log('#inviteForm.submit')
    let form = $(this)
    console.log(form)
    $.ajax({
        url: form.attr('action'),
        type: form.attr('method'),
        data: new FormData(this),
        success: function (data) {
            console.log('data: ' + data)
            location.reload()
        },
        error: function (jqXHR) {
            console.log('jqXHR.status: ' + jqXHR.status)
            console.log('jqXHR.statusText: ' + jqXHR.statusText)
            if (jqXHR.status === 400) {
                let data = jqXHR.responseJSON
                console.log(data)
                $(form.prop('elements')).each(function () {
                    if (data.hasOwnProperty(this.name)) {
                        $('#' + this.name + '-invalid')
                            .empty()
                            .append(data[this.name])
                        $(this).addClass('is-invalid')
                    }
                })
            } else {
                let message = jqXHR.status + ': ' + jqXHR.statusText
                show_toast(message, 'danger', '6000')
            }
        },
        cache: false,
        contentType: false,
        processData: false,
    })
})

// Handle invite code searches
$('#inviteSearch').on('submit', function (event) {
    event.preventDefault()
    let invite = $(this)[0].invite.value.trim()
    let action = $(this).attr('action')
    return window.location.replace(action + invite)
})
