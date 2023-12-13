// JS for Embed Password

// Password form handler
$('#password-form').on('submit', function (event) {
    event.preventDefault()
    if ($('#password-button').hasClass('disabled')) {
        return
    }
    $.ajax({
        url: $('#password-form').attr('action'),
        type: 'POST',
        data: new FormData($(this)),
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
            $('#password-form input').addClass('is-invalid')
        },
        complete: function () {
            console.log('complete')
            $('#password-button').removeClass('disabled')
        },
        cache: false,
        contentType: false,
        processData: false,
    })
})
