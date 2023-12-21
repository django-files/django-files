// JS for Keyboard Shortcuts

const keyLocations = {
    KeyA: '/uppy/',
    KeyS: '/settings/user/',
    KeyD: '/settings/site/',
    KeyF: '/files/',
    KeyG: '/gallery/',
    KeyH: '/',
    KeyR: '/shorts/',
    KeyT: '/paste/',
    KeyY: '/admin/settings/sitesettings/1/change/',
    KeyX: '/settings/sharex/',
}

window.addEventListener('keydown', (e) => {
    // console.log('handleKeyboard:', e)
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || e.repeat) {
        return
    }
    const tagNames = ['INPUT', 'TEXTAREA', 'SELECT', 'OPTION']
    if (tagNames.includes(e.target.tagName)) {
        return
    }
    if (keyLocations[e.code]) {
        window.location = keyLocations[e.code]
    } else if (['KeyZ', 'KeyK'].includes(e.code)) {
        $('#keybinds-modal').modal('toggle')
    }
})
