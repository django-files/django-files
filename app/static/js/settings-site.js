// JS for settings/site.html

const deleteSessionsModal = $('#delete-sessions-modal')

const backgroundPicture = document.getElementById('background_picture_group')
const backgroundVideo = document.getElementById('background_video_group')

document.addEventListener('DOMContentLoaded', domContentLoaded)
document
    .getElementsByName('login_background')
    .forEach((el) => el.addEventListener('change', loginBackgroundChange))
document
    .querySelectorAll('[data-session]')
    .forEach((el) => el.addEventListener('click', deleteSession))

const deleteAllSessionsBtn = document.getElementById('delete-all-sessions')
deleteAllSessionsBtn.addEventListener('click', (e) => deleteSession(e, true))

/**
 * DOMContentLoaded Callback
 * @function domContentLoaded
 */
async function domContentLoaded() {
    console.debug('DOMContentLoaded: settings-site.js')
    const selected = document.querySelector(
        'input[name="login_background"]:checked'
    )
    console.debug('selected:', selected.value)
    updateBackgroundInput(selected.value)
}

/**
 * Login Background Change Callback
 * @function loginBackgroundChange
 * @param {Event} event
 */
function loginBackgroundChange(event) {
    console.debug('loginBackgroundChange:', event.target.value)
    updateBackgroundInput(event.target.value)
}

/**
 * Update Login Background
 * @function loginBackgroundChange
 * @param {String} value
 */
function updateBackgroundInput(value) {
    if (value === 'picture') {
        backgroundVideo.classList.add('d-none')
        backgroundPicture.classList.remove('d-none')
    } else if (value === 'video') {
        backgroundPicture.classList.add('d-none')
        backgroundVideo.classList.remove('d-none')
    } else {
        backgroundPicture.classList.add('d-none')
        backgroundVideo.classList.add('d-none')
    }
}

async function deleteSession(event, all = false) {
    console.debug('deleteSession:', event)
    const target = event.currentTarget
    // console.debug('target:', target)
    // console.debug('tr:', tr)
    const sessionId = all ? 'all' : target.dataset.session
    console.debug('sessionId:', sessionId)
    const siteUrl = document.getElementById('site_settings-site_url').value
    const url = `${siteUrl}/api/session/${sessionId}`
    console.debug('url:', url)
    const response = await fetch(url, { method: 'DELETE' })
    console.debug('response.status:', response.status)
    if (response.status === 201) {
        if (all) {
            document
                .getElementById('sessions-table')
                .querySelector('tbody')
                .querySelectorAll('tr')
                .forEach((el) => {
                    if (!el.classList.contains('table-active')) {
                        console.log('deleting row:', el)
                        el.remove()
                    }
                })
            deleteSessionsModal.modal('hide')
            const code = deleteSessionsModal.find('code')
            // const count = parseInt(code.text(), 10)
            // code.text(count - 1)
            const count = +code.text() - 1
            code.text(count)
            if (count < 1) {
                deleteAllSessionsBtn.classList.add('d-none')
            }
        } else {
            const el = target.closest('tr')
            console.log('deleting row:', el)
            el.remove()
        }
        show_toast('Session Deleted.')
    } else if (response.status === 404) {
        show_toast('Session Not Found.')
    } else if (response.status === 400) {
        const text = await response.text()
        show_toast(text)
    } else {
        show_toast('Error Deleting Session.', 'danger')
    }
}
