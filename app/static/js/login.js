// JS for Login

$('#login-form').on('submit', function (event) {
    event.preventDefault()
    if ($('#login-button').hasClass('disabled')) {
        return
    }
    $.ajax({
        url: $('#login-form').attr('action'),
        type: 'POST',
        data: new FormData(this),
        crossDomain: true,
        beforeSend: function () {
            $('#login-button').addClass('disabled')
        },
        success: function (response) {
            console.log('response: ' + response)
            if (response.redirect) {
                console.log('response.redirect: ' + response.redirect)
                // window.location.href = response.redirect
                return window.location.replace(response.redirect)
            }
            location.reload()
        },
        error: function (xhr, status, error) {
            console.log('xhr: ' + xhr)
            console.log('status: ' + status)
            console.log('error: ' + error)
            $('#login-form input').addClass('is-invalid')
        },
        complete: function () {
            console.log('complete')
            $('#login-button').removeClass('disabled')
        },
        cache: false,
        contentType: false,
        processData: false,
    })
})
