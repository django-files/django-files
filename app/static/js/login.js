// JS for Login

$('#login-form').on('submit', function (event) {
    console.log('#login-form submit', event)
    event.preventDefault()
    const loginButton = $('#login-button')
    if (loginButton.hasClass('disabled')) {
        return console.warn('Double Click Prevented!')
    }
    $.ajax({
        type: 'POST',
        url: $('#login-form').attr('action'),
        data: new FormData(this),
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

document.addEventListener('DOMContentLoaded', function () {
    const loginBackground = JSON.parse(
        document.getElementById('login_background').textContent
    )
    console.debug('loginBackground:', loginBackground)
    const backgroundPicture = JSON.parse(
        document.getElementById('background_picture').textContent
    )
    console.debug('backgroundPicture:', backgroundPicture)
    let options = {}
    if (loginBackground === 'picture') {
        console.debug('setBackground:', options)
        document.body.style.background = `url('${backgroundPicture}') no-repeat center fixed`
        document.body.style.backgroundSize = 'cover'
        document.querySelector('video').classList.add('d-none')
    } else if (loginBackground === 'video') {
        document.querySelector('video').classList.remove('d-none')
        document.body.style.cssText = ''
    } else {
        document.body.style.cssText = ''
        document.querySelector('video').classList.add('d-none')
    }

    tsParticles
        .load({
            id: 'tsparticles',
            url: '/static/config/tsparticles.json',
        })
        .then((container) => {
            console.log('tsparticles loaded:', container)
        })
})
