// JS for Keyboard Shortcuts

const keyLocations = {
    KeyA: '/uppy/',
    KeyD: '/settings/site/',
    KeyF: '/files/',
    KeyG: '/gallery/',
    KeyH: '/',
    KeyR: '/shorts/',
    KeyS: '/settings/user/',
    KeyT: '/paste/',
    KeyX: '/settings/sharex/',
    KeyY: '/admin/settings/sitesettings/1/change/',
}

const tagNames = ['INPUT', 'TEXTAREA', 'SELECT', 'OPTION']

window.addEventListener('keydown', (e) => {
    // console.log('handleKeyboard:', e)
    if (
        e.altKey ||
        e.ctrlKey ||
        e.metaKey ||
        e.shiftKey ||
        e.repeat ||
        tagNames.includes(e.target.tagName)
    ) {
        return
    }
    if (['KeyZ', 'KeyK'].includes(e.code)) {
        $('#keybinds-modal').modal('toggle')
    } else if (keyLocations[e.code]) {
        window.location = keyLocations[e.code]
    }
})
