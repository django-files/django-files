// JS for Site Settings

console.debug('LOADING: settings.js')

const deleteDiscordHookModal = $('#deleteDiscordHookModal')
const fileUploadModal = $('#avatarUploadModal')
const settingsForm = $('#settingsForm')

settingsForm.on('change', saveOptions)

// document.addEventListener('dragenter', (event) => {
//     event.preventDefault()
//     fileUploadModal.modal('show')
// })

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

const getStoredTheme = () => localStorage.getItem('theme')
const setStoredTheme = theme => localStorage.setItem('theme', theme)

const getPreferredTheme = () => {
  const storedTheme = getStoredTheme()
  if (storedTheme) {
    return storedTheme
  }

  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

const setTheme = theme => {
  if (theme === 'auto') {
    document.documentElement.setAttribute('data-bs-theme', (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'))
  } else {
    document.documentElement.setAttribute('data-bs-theme', theme)
  }
}

setTheme(getPreferredTheme())

const showActiveTheme = (theme, focus = false) => {
  const themeSwitcher = document.querySelector('#bd-theme')

  if (!themeSwitcher) {
    return
  }

  const themeSwitcherText = document.querySelector('#bd-theme-text')
  const activeThemeIcon = document.querySelector('.theme-icon-active use')
  const btnToActive = document.querySelector(`[data-bs-theme-value="${theme}"]`)
  const svgOfActiveBtn = btnToActive.querySelector('svg use').getAttribute('href')

  document.querySelectorAll('[data-bs-theme-value]').forEach(element => {
    element.classList.remove('active')
    element.setAttribute('aria-pressed', 'false')
  })

  btnToActive.classList.add('active')
  btnToActive.setAttribute('aria-pressed', 'true')
  activeThemeIcon.setAttribute('href', svgOfActiveBtn)
  const themeSwitcherLabel = `${themeSwitcherText.textContent} (${btnToActive.dataset.bsThemeValue})`
  themeSwitcher.setAttribute('aria-label', themeSwitcherLabel)

  if (focus) {
    themeSwitcher.focus()
  }
}

window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
  const storedTheme = getStoredTheme()
  if (storedTheme !== 'light' && storedTheme !== 'dark') {
    setTheme(getPreferredTheme())
  }
})

window.addEventListener('DOMContentLoaded', () => {
  showActiveTheme(getPreferredTheme())

  document.querySelectorAll('#data-bs-theme-value')
    .forEach(toggle => {
      toggle.addEventListener('click', () => {
        const theme = (getStoredTheme() || toggle.getAttribute('data-bs-theme-value')) == 'light' ? 'dark' : 'light'
        setStoredTheme(theme)
        setTheme(theme)
        showActiveTheme(theme, true)
      })
    })
})