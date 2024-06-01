// JS for Site Settings

console.debug('LOADING: settings.js')

const deleteDiscordHookModal = $('#deleteDiscordHookModal')
const fileUploadModal = $('#avatarUploadModal')
const settingsForm = $('#settingsForm')

const themeToggle = document.getElementById('theme-toggle')
const newThemeValue = document.getElementById('new-theme-value')

document.addEventListener('DOMContentLoaded', domContentLoaded)
themeToggle.addEventListener('click', toggleThemeSwitch)
settingsForm.on('change', saveOptions)

/**
 * DOMContentLoaded Callback
 * @function domContentLoaded
 */
async function domContentLoaded() {
    console.debug('DOMContentLoaded')
    const storedTheme = localStorage.getItem('theme')
    if (storedTheme) {
        themeToggle.checked = true
    }
    const prefers = window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'Light'
        : 'Dark'
    console.log('prefers:', prefers)
    newThemeValue.textContent = prefers
}

function toggleThemeSwitch() {
    const query = window.matchMedia('prefers-color-scheme: dark')
    console.info('data-bs-theme-value', query)

    const storedTheme = localStorage.getItem('theme')
    console.info('storedTheme:', storedTheme)
    let prefers
    if (storedTheme) {
        prefers = storedTheme === 'light' ? 'dark' : 'light'
        console.debug('reverting to auto theme')
        localStorage.removeItem('theme')
    } else {
        prefers = window.matchMedia('(prefers-color-scheme: dark)').matches
            ? 'light'
            : 'dark'
        console.log('forcing opposite theme:', prefers)
        localStorage.setItem('theme', prefers)
    }
    document.documentElement.setAttribute('data-bs-theme', prefers)
}

// TODO: Use a proper selector
let hookID
$('.deleteDiscordHookBtn').on('click', function (event) {
    console.log('.deleteDiscordHookBtn click', event)
    hookID = $(this).data('hook-id')
    console.log(hookID)
    deleteDiscordHookModal.modal('show')
})

$('.uploadAvatarHookBtn').on('click', function (event) {
    console.log('.uploadAvatarHookBtn click', event)
    hookID = $(this).data('hook-id')
    console.log(hookID)
    fileUploadModal.modal('show')
})

// Handle Confirm Delete Clicks
$('#confirmDeleteDiscordHookBtn').on('click', function (event) {
    console.log('#confirmDeleteDiscordHookBtn click', event)
    console.log(`hookID: ${hookID}`)
    $.ajax({
        type: 'POST',
        url: `/ajax/delete/hook/${hookID}/`,
        headers: { 'X-CSRFToken': csrftoken },
        success: function (data) {
            console.log('data:', data)
            deleteDiscordHookModal.modal('hide')
            console.log(`removing #wehook-${hookID}`)
            const count = $('#discordWebhooksTable tr').length
            $(`#webhook-${hookID}`).remove()
            if (count <= 2) {
                console.log('removing #discordWebhooksTable@')
                $('#discordWebhooksTable').remove()
            }
            const message = `Webhoook ${hookID} Successfully Removed.`
            show_toast(message, 'success')
        },
        error: function (jqXHR) {
            deleteDiscordHookModal.modal('hide')
            messageErrorHandler(jqXHR)
        },
        cache: false,
        contentType: false,
        processData: false,
    })
})

// Handle Invites Form
$('#invitesForm').on('submit', function (event) {
    console.log('#invitesForm submit', event)
    event.preventDefault()
    const form = $(this)
    console.log('form:', form)
    const data = new FormData(this)
    data.forEach((value, key) => (data[key] = value))
    $.ajax({
        type: form.attr('method'),
        url: form.attr('action'),
        data: JSON.stringify(data),
        headers: { 'X-CSRFToken': csrftoken },
        success: function (data) {
            console.log('data:', data)
            alert(`Invite Created: ${data.invite}`)
            location.reload()
        },
        error: messageErrorHandler,
        cache: false,
        contentType: false,
        processData: false,
    })
})

// Handle Update Checks
$('#check-for-update').on('click', function (event) {
    console.log('#check-for-update click', event)
    const data = JSON.stringify({ method: 'check-for-update' })
    console.log('data:', data)
    socket.send(data)
})
