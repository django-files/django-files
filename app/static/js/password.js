// JS for Embed Password

// $('#password-form').on('submit', function (event) {
//     window.location.replace($('#password-form').attr('action'))
// })

$('#password-form').on('submit', function (event) {
    console.log('#password-form submit', event)
    event.preventDefault()
    const passwordButton = $('#password-button')
    if (passwordButton.hasClass('disabled')) {
        return
    }
    const password = $('#password').val()
    $.ajax({
        type: 'POST',
        url: $('#password-form').attr('action'),
        data: new FormData(this),
        beforeSend: function () {
            passwordButton.addClass('disabled')
        },
        success: function (data) {
            console.log('data:', data)
            const url = new URL(
                window.location.origin + window.location.pathname
            )
            url.searchParams.append('password', password)
            window.location.replace(url.href)
        },
        error: function (jqXHR) {
            console.log('jqXHR:', jqXHR)
            $('#password-form input').addClass('is-invalid')
            show_toast('Invalid Password.', 'warning')
        },
        complete: function () {
            passwordButton.removeClass('disabled')
        },
        cache: false,
        contentType: false,
        processData: false,
    })
})
