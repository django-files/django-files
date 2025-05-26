// JS for settings/user.html

// const themeToggle = document.getElementById('theme-toggle')
// const newThemeValue = document.getElementById('new-theme-value')

document.addEventListener('DOMContentLoaded', domContentLoaded)
// themeToggle.addEventListener('click', toggleThemeSwitch)

/**
 * DOMContentLoaded Callback
 * @function domContentLoaded
 */
async function domContentLoaded() {
    console.debug('DOMContentLoaded: settings-user.js')
    // const storedTheme = localStorage.getItem('theme')
    // console.debug('storedTheme:', storedTheme)
    // if (storedTheme && storedTheme !== 'auto') {
    //     themeToggle.checked = true
    // }
    // const prefers = window.matchMedia('(prefers-color-scheme: dark)').matches
    //     ? 'Light'
    //     : 'Dark'
    // console.log('prefers:', prefers)
    // newThemeValue.textContent = prefers
}

// function toggleThemeSwitch() {
//     const query = window.matchMedia('prefers-color-scheme: dark')
//     console.info('data-bs-theme-value', query)
//
//     const storedTheme = localStorage.getItem('theme')
//     console.info('storedTheme:', storedTheme)
//     let prefers
//     if (storedTheme) {
//         prefers = storedTheme === 'light' ? 'dark' : 'light'
//         console.debug('reverting to auto theme')
//         localStorage.removeItem('theme')
//     } else {
//         prefers = window.matchMedia('(prefers-color-scheme: dark)').matches
//             ? 'light'
//             : 'dark'
//         console.log('forcing opposite theme:', prefers)
//         localStorage.setItem('theme', prefers)
//     }
//     document.documentElement.setAttribute('data-bs-theme', prefers)
// }

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
            document.getElementById('primary-token').innerText = token // Update the HTML element
        })
        .then((data) => console.log('Success:', data))
        .catch((error) => console.log('Error:', error))
}

const qrCodeBtn = document.getElementById('show-qrcode')
qrCodeBtn.addEventListener('click', showQrCode)

async function showQrCode(event) {
    event.preventDefault()
    console.log('event:', event)
    const div = document.getElementById('qrcode-div')
    const link = document.getElementById('qrcode-link')
    console.log('link:', link)
    console.log('link.href:', link.href)
    const img = document.createElement('img')
    img.src = link.dataset.qrcode
    img.alt = 'QR Code'
    img.classList.add('img-fluid')
    link.appendChild(img)
    qrCodeBtn.remove()
    div.classList.remove('d-none')
    const span = div.querySelector('span')
    const top = img.getBoundingClientRect().top + window.scrollY - 120
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
}
