// JS for settings/user.html

const showCodeBtn = document.getElementById('showCodeBtn')
const hideCodeBtn = document.getElementById('hideCodeBtn')
const cameraIcon = document.getElementById('cameraIcon')
const codeDiv = document.getElementById('qrcode-div')
const codeLink = document.getElementById('qrcode-link')

document.addEventListener('DOMContentLoaded', domContentLoaded)
showCodeBtn.addEventListener('click', showQrCode)
hideCodeBtn.addEventListener('click', hideQrCode)

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

setupPasswordMatch(
    document.getElementById('new_password'),
    document.getElementById('confirm_new_password'),
    document.getElementById('confirm_new_password-invalid')
)

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

const disableLocalAuthModalEl = document.getElementById('disableLocalAuthModal')
const confirmDisableLocalAuthBtn = document.getElementById(
    'confirmDisableLocalAuthBtn'
)

localAuthToggle?.addEventListener('change', (event) => {
    if (!event.target.checked) {
        // Re-enabling requires a password — open the password modal instead.
        event.target.checked = true
        bootstrap.Modal.getOrCreateInstance(passwordChangeModalEl).show()
        return
    }
    // Show confirmation modal; revert toggle until confirmed.
    event.target.checked = false
    bootstrap.Modal.getOrCreateInstance(disableLocalAuthModalEl).show()
})

confirmDisableLocalAuthBtn?.addEventListener('click', async () => {
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
    bootstrap.Modal.getOrCreateInstance(disableLocalAuthModalEl).hide()
    if (response.ok) {
        if (localAuthToggle) localAuthToggle.checked = true
        show_toast('Local login disabled.', 'success')
    } else {
        const data = await response.json().catch(() => ({}))
        show_toast(
            data.error || `${response.status}: ${response.statusText}`,
            'danger'
        )
    }
})

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

const deleteAccountBtn = document.getElementById('deleteAccountBtn')
const deleteAccountModalEl = document.getElementById('deleteAccountModal')
const deleteAccountConfirmInput = document.getElementById(
    'deleteAccountConfirmInput'
)
const confirmDeleteAccountBtn = document.getElementById(
    'confirmDeleteAccountBtn'
)
const deleteAccountPhrase = document
    .getElementById('deleteAccountPhrase')
    ?.textContent?.trim()

deleteAccountBtn?.addEventListener('click', () => {
    deleteAccountConfirmInput.value = ''
    deleteAccountConfirmInput.classList.remove('is-invalid')
    document.getElementById('deleteAccountConfirmFeedback').textContent = ''
    confirmDeleteAccountBtn.disabled = true
    bootstrap.Modal.getOrCreateInstance(deleteAccountModalEl).show()
    deleteAccountModalEl.addEventListener(
        'shown.bs.modal',
        () => deleteAccountConfirmInput.focus(),
        { once: true }
    )
})

deleteAccountConfirmInput?.addEventListener('input', () => {
    const matches =
        deleteAccountConfirmInput.value.trim() === deleteAccountPhrase
    confirmDeleteAccountBtn.disabled = !matches
    if (matches) {
        deleteAccountConfirmInput.classList.remove('is-invalid')
    }
})

confirmDeleteAccountBtn?.addEventListener('click', async () => {
    const phrase = deleteAccountConfirmInput.value.trim()
    if (phrase !== deleteAccountPhrase) {
        deleteAccountConfirmInput.classList.add('is-invalid')
        document.getElementById('deleteAccountConfirmFeedback').textContent =
            'Confirmation phrase did not match.'
        return
    }
    const csrfToken = document.querySelector(
        'input[name="csrfmiddlewaretoken"]'
    ).value
    const body = new FormData()
    body.append('confirm_phrase', phrase)
    confirmDeleteAccountBtn.disabled = true
    confirmDeleteAccountBtn.innerHTML =
        '<span class="spinner-border spinner-border-sm me-2"></span>Deleting...'
    const response = await fetch('/settings/user/delete', {
        method: 'POST',
        body: body,
        headers: { 'X-CSRFToken': csrfToken },
    })
    if (response.ok) {
        const data = await response.json()
        window.location.href = data.duo_redirect || data.redirect || '/'
    } else {
        const data = await response.json().catch(() => ({}))
        deleteAccountConfirmInput.classList.add('is-invalid')
        document.getElementById('deleteAccountConfirmFeedback').textContent =
            data.error || `${response.status}: ${response.statusText}`
        confirmDeleteAccountBtn.disabled = false
        confirmDeleteAccountBtn.innerHTML =
            '<i class="fa-solid fa-trash me-2"></i>Permanently Delete My Account'
    }
})

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
