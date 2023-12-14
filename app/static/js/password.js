// JS for Embed Password

$('#password-form').on('submit', function (event) {
    console.log('#password-form submit', event)
    event.preventDefault()
    const passwordButton = $('#password-button')
    if (passwordButton.hasClass('disabled')) {
        return
    }
    $.ajax({
        url: $('#password-form').attr('action'),
        type: 'POST',
        data: new FormData($(this)),
        crossDomain: true,
        beforeSend: function () {
            passwordButton.addClass('disabled')
        },
        success: function (data) {
            console.log('data:', data)
            if (data.redirect) {
                console.log(`data.redirect: ${data.redirect}`)
                // window.location.href = data.redirect
                return window.location.replace(data.redirect)
            }
            location.reload()
        },
        error: function (jqXHR) {
            console.log('jqXHR:', jqXHR)
            $('#password-form input').addClass('is-invalid')
        },
        complete: function () {
            passwordButton.removeClass('disabled')
        },
        cache: false,
        contentType: false,
        processData: false,
    })
})
