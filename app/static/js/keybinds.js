function checkKey(event) {
    const formElements = ['INPUT', 'TEXTAREA', 'SELECT', 'OPTION']
    if (!formElements.includes(event.target.tagName)) {
        console.log(event.keyCode)
        if (event.keyCode === 65) {
            window.location = '/uppy/' // A
        } else if (event.keyCode === 83) {
            window.location = '/settings/user/' // S
        } else if (event.keyCode === 68) {
            window.location = '/settings/site/' // D
        } else if (event.keyCode === 70) {
            window.location = '/files/' // F
        } else if (event.keyCode === 71) {
            window.location = '/gallery/' // G
        } else if (event.keyCode === 72) {
            window.location = '/' // H
        } else if (event.keyCode === 82) {
            window.location = '/shorts/' // R
        } else if (event.keyCode === 84) {
            window.location = '/paste/' // T
        } else if (event.keyCode === 89) {
            window.location = '/admin/settings/sitesettings/1/change/' // Y
        } else if (event.keyCode === 88) {
            window.location = '/settings/sharex/' // X
        } else if (event.keyCode === 75 || event.keyCode === 90) {
            $('#keybinds-modal').modal('toggle') // K
        }
    }
}

// Listen for keydown events
window.addEventListener('keydown', checkKey)
