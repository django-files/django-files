// JS for settings/site.html

const backgroundPicture = document.getElementById('background_picture_group')
const backgroundVideo = document.getElementById('background_video_group')

document.addEventListener('DOMContentLoaded', domContentLoaded)
document
    .getElementsByName('login_background')
    .forEach((el) => el.addEventListener('change', loginBackgroundChange))

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
