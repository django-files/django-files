$(document).ready(function () {
    // Show Welcome Modal
    let welcomeModal = new bootstrap.Modal('#welcomeModal', {})
    welcomeModal.show()

    // Welcome Form Handler
    $('#welcomeForm').on('submit', function (event) {
        console.log('saveCredentials on click function')
        event.preventDefault()
        let form = $(this)
        // let welcomeForm = $('#welcomeForm')
        let formData = new FormData(form[0])
        $.ajax({
            url: form.attr('action'),
            type: 'POST',
            data: formData,
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

    $('#welcomeModal').on('shown.bs.modal', function () {
        $('#password').focus()
    })
})
