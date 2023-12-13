// JS for Welcome
// TODO: Look into cleaning up welcomeModal definitions

$(window).on('load', function () {
    let welcomeModal = new bootstrap.Modal('#welcomeModal', {})
    welcomeModal.show()
})

$('#welcomeModal').on('shown.bs.modal', function () {
    const timeZone = new window.Intl.DateTimeFormat().resolvedOptions().timeZone
    $('#timezone').val(timeZone)
    $('#password').trigger('focus')
})

$('#welcomeForm').on('submit', function (event) {
    event.preventDefault()
    console.log('#welcomeForm.submit', event)
    let form = $(this)
    // let welcomeForm = $('#welcomeForm')
    $.ajax({
        url: form.attr('action'),
        type: 'POST',
        data: new FormData(this),
        success: function (response) {
            console.log('response: ' + response)
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
        complete: function () {
            console.log('complete')
        },
        cache: false,
        contentType: false,
        processData: false,
    })
})
