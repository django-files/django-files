// JS for settings/user.html

const showCodeBtn = document.getElementById('showCodeBtn')
const hideCodeBtn = document.getElementById('hideCodeBtn')
const cameraIcon = document.getElementById('cameraIcon')
const showTokenBtn = document.getElementById('showTokenBtn')
const codeDiv = document.getElementById('qrcode-div')
const codeLink = document.getElementById('qrcode-link')
const primaryToken = document.getElementById('primary-token')

document.addEventListener('DOMContentLoaded', domContentLoaded)
showCodeBtn.addEventListener('click', showQrCode)
hideCodeBtn.addEventListener('click', hideQrCode)
showTokenBtn.addEventListener('click', toggleToken)
document.getElementById('tokenRefreshBtn').addEventListener('click', () => {
    bootstrap.Modal.getOrCreateInstance(
        document.getElementById('tokenRegenerateModal')
    ).show()
})
document
    .getElementById('confirmTokenRegenerateBtn')
    .addEventListener('click', () => {
        bootstrap.Modal.getOrCreateInstance(
            document.getElementById('tokenRegenerateModal')
        ).hide()
        tokenRefresh()
    })

showCodeBtn.addEventListener('mouseover', () =>
    cameraIcon.classList.add('fa-beat')
)
showCodeBtn.addEventListener('mouseout', () =>
    cameraIcon.classList.remove('fa-beat')
)

/**
 * DOMContentLoaded Callback
 * @function domContentLoaded
 */
async function domContentLoaded() {
    console.debug('DOMContentLoaded: settings-user.js')
    //qrCode.download({ name: 'qr', extension: 'svg' })
}

const changePasswordBtn = document.getElementById('changePasswordBtn')
const passwordChangeModalEl = document.getElementById('passwordChangeModal')
const passwordChangeForm = document.getElementById('passwordChangeForm')
const localAuthToggle = document.getElementById('local_auth_disabled')

changePasswordBtn?.addEventListener('click', () => {
    passwordChangeForm.reset()
    clearPasswordErrors()
    bootstrap.Modal.getOrCreateInstance(passwordChangeModalEl).show()
})

const newPasswordInput = document.getElementById('new_password')
const confirmPasswordInput = document.getElementById('confirm_new_password')
const confirmFeedback = document.getElementById('confirm_new_password-invalid')

function checkPasswordMatch() {
    if (!confirmPasswordInput) return
    if (!confirmPasswordInput.value) {
        confirmPasswordInput.classList.remove('is-invalid')
        if (confirmFeedback) confirmFeedback.textContent = ''
        return
    }
    if (confirmPasswordInput.value === newPasswordInput.value) {
        confirmPasswordInput.classList.remove('is-invalid')
        if (confirmFeedback) confirmFeedback.textContent = ''
    } else {
        confirmPasswordInput.classList.add('is-invalid')
        if (confirmFeedback)
            confirmFeedback.textContent = 'Passwords do not match.'
    }
}

confirmPasswordInput?.addEventListener('input', checkPasswordMatch)
newPasswordInput?.addEventListener('input', checkPasswordMatch)

passwordChangeForm?.addEventListener('submit', async (event) => {
    event.preventDefault()
    clearPasswordErrors()
    const data = new FormData(passwordChangeForm)
    const csrfToken = data.get('csrfmiddlewaretoken')
    const response = await fetch('/settings/user/password', {
        method: 'POST',
        body: data,
        headers: { 'X-CSRFToken': csrfToken },
    })
    if (response.ok) {
        bootstrap.Modal.getOrCreateInstance(passwordChangeModalEl).hide()
        show_toast('Password updated.', 'success')
        if (localAuthToggle) localAuthToggle.checked = false
    } else if (response.status === 400) {
        const errors = await response.json()
        for (const [field, message] of Object.entries(errors)) {
            const input = passwordChangeForm.querySelector(`[name="${field}"]`)
            const feedback = document.getElementById(`${field}-invalid`)
            if (input) input.classList.add('is-invalid')
            if (feedback) feedback.textContent = message
        }
    } else {
        show_toast(`${response.status}: ${response.statusText}`, 'danger')
    }
})

function clearPasswordErrors() {
    passwordChangeForm
        ?.querySelectorAll('.is-invalid')
        .forEach((el) => el.classList.remove('is-invalid'))
    passwordChangeForm
        ?.querySelectorAll('.invalid-feedback')
        .forEach((el) => (el.textContent = ''))
}

localAuthToggle?.addEventListener('change', async (event) => {
    if (!event.target.checked) {
        // Re-enabling requires a password — open the modal instead.
        event.target.checked = true
        bootstrap.Modal.getOrCreateInstance(passwordChangeModalEl).show()
        return
    }
    const csrfToken = document.querySelector(
        'input[name="csrfmiddlewaretoken"]'
    ).value
    const body = new FormData()
    body.append('disable', 'true')
    const response = await fetch('/settings/user/local-auth', {
        method: 'POST',
        body: body,
        headers: { 'X-CSRFToken': csrfToken },
    })
    if (response.ok) {
        show_toast('Local login disabled.', 'success')
    } else {
        event.target.checked = false
        show_toast(`${response.status}: ${response.statusText}`, 'danger')
    }
})

function toggleToken(event) {
    event.preventDefault()
    console.log('toggleToken:', event)
    primaryToken.classList.toggle('settings-token-blurred')
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

let codeTimer

async function hideQrCode(event) {
    event.preventDefault()
    console.log('hideQrCode:', event)
    codeLink.innerHTML = ''
    clearInterval(codeTimer)
    hideCodeBtn.classList.add('d-none')
    showCodeBtn.classList.remove('d-none')
    codeDiv.classList.add('d-none')
    const span = codeDiv.querySelector('span')
    span.textContent = '10:00'
}

async function showQrCode(event) {
    event.preventDefault()
    console.log('showQrCode:', event)
    cameraIcon.classList.replace('fa-beat', 'fa-flip')
    console.log('link:', codeLink)
    console.log('codeLink.href:', codeLink.href)
    fetch('/settings/user/signature').then((response) =>
        response.json().then((data) => {
            console.log('data:', data)
            codeLink.href = data.url
            console.log('codeLink.href:', codeLink.href)
            const qrCode = genQrCode(codeLink.href)
            qrCode.append(codeLink)
            codeLink.querySelector('svg').classList.add('img-fluid')
            codeDiv.classList.remove('d-none')
            const span = codeDiv.querySelector('span')
            const top =
                codeDiv.getBoundingClientRect().top + window.scrollY - 100
            window.scrollTo({ top, behavior: 'smooth' })
            let totalSeconds = 599
            codeTimer = setInterval(() => {
                const minutes = Math.floor(totalSeconds / 60)
                const seconds = totalSeconds % 60
                span.textContent = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
                if (totalSeconds === 0) {
                    span.classList.replace(
                        'text-success-emphasis',
                        'text-danger-emphasis'
                    )
                    clearInterval(codeTimer)
                } else {
                    totalSeconds--
                }
            }, 1000)

            cameraIcon.classList.remove('fa-beat', 'fa-flip')
            bootstrap.Tooltip.getInstance(showCodeBtn)?.hide()
            showCodeBtn.classList.add('d-none')
            hideCodeBtn.classList.remove('d-none')
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
    if (theme !== 'dark' && theme !== 'light') {
        theme = window.matchMedia('(prefers-color-scheme: dark)').matches
            ? 'dark'
            : 'light'
    }
    console.log('theme:', theme)
    return theme === 'dark'
}
