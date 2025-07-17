// JS for Login

const loginButton = $('#login-button')
const loginOuter = $('#login-outer')

loginOuter.one('animationend', () => {
    console.debug('loginOuter: animationend')
    loginOuter.removeClass(['animate__animated', 'animate__backInDown'])
})

$(window).on('pageshow', () => {
    loginOuter.removeClass([
        'animate__animated',
        'animate__backOutUp',
        'animate__slow',
    ])
    loginOuter.addClass([
        'animate__animated',
        'animate__backInDown',
        'animate__fast',
    ])
})

$('#login-buttons > .login').on('click', () => {
    loginOuter.addClass([
        'animate__animated',
        'animate__backOutUp',
        'animate__slow',
    ])
})

$('#login-form').on('submit', function (event) {
    console.log('#login-form submit', event)
    event.preventDefault()
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
            loginOuter.addClass([
                'animate__animated',
                'animate__backOutUp',
                'animate__slow',
            ])
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
            animateCSS('#local-inputs', 'shakeX')
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

    const tsparticlesEnabled = JSON.parse(
        document.getElementById('tsparticles_enabled').textContent
    )
    console.debug('tsparticlesEnabled:', tsparticlesEnabled)
    const tsparticlesConfig =
        JSON.parse(document.getElementById('tsparticles_config').textContent) ||
        '/static/config/tsparticles.json'
    console.debug('tsparticlesConfig:', tsparticlesConfig)
    if (tsparticlesEnabled) {
        tsParticles
            .load({
                id: 'tsparticles',
                url: tsparticlesConfig,
            })
            .then((container) => {
                console.log('tsparticles loaded:', container)
            })
    }
})

const animateCSS = (selector, animation, prefix = 'animate__') => {
    const name = `${prefix}${animation}`
    const node = document.querySelector(selector)
    node.classList.add(`${prefix}animated`, name)
    function handleAnimationEnd(event) {
        event.stopPropagation()
        node.classList.remove(`${prefix}animated`, name)
    }
    node.addEventListener('animationend', handleAnimationEnd, {
        once: true,
    })
}
