// JS for Login

$('#login-form').on('submit', function (event) {
    console.log('#login-form on submit', event)
    event.preventDefault()
    const loginButton = $('#login-button')
    if (loginButton.hasClass('disabled')) {
        return
    }
    $.ajax({
        url: $('#login-form').attr('action'),
        type: 'POST',
        data: new FormData(this),
        crossDomain: true,
        beforeSend: function () {
            loginButton.addClass('disabled')
        },
        success: function (data) {
            console.log('data:', data)
            if (data.redirect) {
                console.log(`data.redirect: ${data.redirect}`)
                // window.location.href = response.redirect
                window.location.replace(data.redirect)
            } else {
                location.reload()
            }
        },
        error: function (jqXHR) {
            console.log('jqXHR:', jqXHR)
            $('#login-form input').addClass('is-invalid')
        },
        complete: function () {
            loginButton.removeClass('disabled')
        },
        cache: false,
        contentType: false,
        processData: false,
    })
})
