$(document).ready(function () {
    // Show Welcome Modal
    let welcomeModal = new bootstrap.Modal('#welcomeModal', {})
    welcomeModal.show()

    // Welcome Form Handler
    $('#saveCredentials').on('click', function (event) {
        console.log('saveCredentials on click function')
        event.preventDefault()
        let welcomeForm = $('#welcomeForm')
        let formData = new FormData(welcomeForm[0])
        $.ajax({
            url: welcomeForm.attr('action'),
            type: 'POST',
            data: formData,
            success: function (response) {
                console.log('response: ' + response)
            },
            error: function (xhr, status, error) {
                console.log('xhr: ' + xhr)
                console.log('status: ' + status)
                console.log('error: ' + error)
            },
            complete: function () {
                console.log('complete')
                location.reload()
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
