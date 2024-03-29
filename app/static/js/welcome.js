// JS for Welcome
// TODO: Look into cleaning up welcomeModal definitions

const welcomeModal = $('#welcomeModal')

document.addEventListener('DOMContentLoaded', function () {
    const siteUrl = $('#site_url')
    if (!siteUrl.val()) {
        console.log('Set site_url from window.location.origin', window.location)
        siteUrl.val(window.location.origin)
    }
    welcomeModal.modal('show')
})

welcomeModal.on('shown.bs.modal', function () {
    const timeZone = new window.Intl.DateTimeFormat().resolvedOptions().timeZone
    console.log('timeZone:', timeZone)
    $('#timezone').val(timeZone)
    $('#password').trigger('focus')
})

$('#welcomeForm').on('submit', function (event) {
    event.preventDefault()
    console.log('#welcomeForm submit', event)
    const form = $(this)
    console.log('form:', form)
    $.ajax({
        type: 'POST',
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
