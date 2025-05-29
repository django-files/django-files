// JS for settings/user.html

const qrCodeBtn = document.getElementById('show-qrcode')
const showTokenBtn = document.getElementById('showTokenBtn')
const primaryToken = document.getElementById('primary-token')

document.addEventListener('DOMContentLoaded', domContentLoaded)
qrCodeBtn.addEventListener('click', showQrCode)
showTokenBtn.addEventListener('click', toggleToken)
document
    .getElementById('tokenRefreshBtn')
    .addEventListener('click', tokenRefresh)

/**
 * DOMContentLoaded Callback
 * @function domContentLoaded
 */
async function domContentLoaded() {
    console.debug('DOMContentLoaded: settings-user.js')
    //qrCode.download({ name: 'qr', extension: 'svg' })
}

function toggleToken(event) {
    event.preventDefault()
    console.log('toggleToken:', event)
    if (primaryToken.style.filter) {
        primaryToken.style.filter = ''
    } else {
        primaryToken.style.filter = 'blur(3px)'
    }
}

function tokenRefresh() {
    const csrfToken = document.querySelector(
        'input[name="csrfmiddlewaretoken"]'
    ).value
    fetch('/api/token/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken },
    })
        .then((response) => response.text())
        .then((token) => {
            document.getElementById('primary-token').textContent = token
        })
        .then((data) => console.log('Success:', data))
        .catch((error) => console.log('Error:', error))
}

async function showQrCode(event) {
    event.preventDefault()
    console.log('showQrCode:', event)
    //if (qrCodeBtn.dataset.hide === 'yes') {
    //    console.log('REMOVE QR CODE')
    //    document.getElementById('qr-code-image').remove()
    //    return
    //}
    const div = document.getElementById('qrcode-div')
    const link = document.getElementById('qrcode-link')
    console.log('link:', link)
    console.log('link.href:', link.href)
    fetch('/settings/user/signature').then((response) =>
        response.json().then((data) => {
            console.log('data:', data)
            link.href = data.url
            console.log('link.href:', link.href)
            const qrCode = genQrCode(link.href)
            qrCode.append(link)
            link.querySelector('svg').classList.add('img-fluid')
            bootstrap.Tooltip.getInstance(qrCodeBtn)?.dispose()
            qrCodeBtn.remove() // TODO: Add Proper Toggle Button...
            div.classList.remove('d-none')
            const span = div.querySelector('span')
            const top = div.getBoundingClientRect().top + window.scrollY - 100
            window.scrollTo({ top, behavior: 'smooth' })
            let totalSeconds = 599
            const timer = setInterval(() => {
                const minutes = Math.floor(totalSeconds / 60)
                const seconds = totalSeconds % 60
                span.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
                if (totalSeconds === 0) {
                    span.classList.replace(
                        'text-success-emphasis',
                        'text-danger-emphasis'
                    )
                    clearInterval(timer)
                } else {
                    totalSeconds--
                }
            }, 1000)
        })
    )
}

function genQrCode(data) {
    return new QRCodeStyling({
        width: 300,
        height: 300,
        type: 'svg',
        data: data,
        image: '/static/images/logo.png',
        margin: 0,
        dotsOptions: {
            color: '#565aa9',
            type: 'extra-rounded',
        },
        cornersDotOptions: {
            color: '#ffffff',
            type: 'extra-rounded',
        },
        cornersSquareOptions: {
            color: '#565aa9',
            type: 'extra-rounded',
        },
        backgroundOptions: {
            color: isDark() ? '#181a1b' : '#e9ebee',
        },
        imageOptions: {
            crossOrigin: 'anonymous',
            margin: 4,
        },
    })
}

function isDark() {
    let theme = localStorage.getItem('theme')
    if (theme !== 'dark' || theme !== 'light') {
        theme = window.matchMedia('(prefers-color-scheme: dark)').matches
            ? 'dark'
            : 'light'
    }
    console.log('theme:', theme)
    return theme === 'dark'
}
