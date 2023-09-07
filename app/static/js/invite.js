$(document).ready(function () {
    // Define Hook Modal and Delete handlers
    let inviteModal = new bootstrap.Modal('#inviteModal', {})
    inviteModal.show()

    // // Local login form handler
    // $('.form-control').focus(function () {
    //     $(this).removeClass('is-invalid')
    // })
    // $('#saveCredentials').on('click', function (event) {
    //     console.log('saveCredentials on click function')
    //     event.preventDefault()
    //     let welcomeForm = $('#welcomeForm')
    //     let formData = new FormData(welcomeForm[0])
    //     $.ajax({
    //         url: welcomeForm.attr('action'),
    //         type: 'POST',
    //         data: formData,
    //         crossDomain: true,
    //         beforeSend: function () {
    //             console.log('beforeSend')
    //         },
    //         success: function (response) {
    //             console.log('response: ' + response)
    //         },
    //         error: function (xhr, status, error) {
    //             console.log('xhr: ' + xhr)
    //             console.log('status: ' + status)
    //             console.log('error: ' + error)
    //         },
    //         complete: function () {
    //             console.log('complete')
    //             location.reload()
    //         },
    //         cache: false,
    //         contentType: false,
    //         processData: false,
    //     })
    // })
})
