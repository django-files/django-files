// JS for Keyboard Shortcuts

window.addEventListener('keydown', (e) => {
    // console.log('handleKeyboard:', e)
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || e.repeat) {
        return
    }
    if (['INPUT', 'TEXTAREA', 'SELECT', 'OPTION'].includes(e.target.tagName)) {
        return
    }
    if (['KeyZ', 'KeyK'].includes(e.code)) {
        $('#keybinds-modal').modal('toggle')
    } else if (e.code === 'KeyA') {
        window.location = '/uppy/'
    } else if (e.code === 'KeyS') {
        window.location = '/settings/user/'
    } else if (e.code === 'KeyD') {
        window.location = '/settings/site/'
    } else if (e.code === 'KeyF') {
        window.location = '/files/'
    } else if (e.code === 'KeyG') {
        window.location = '/gallery/'
    } else if (e.code === 'KeyH') {
        window.location = '/'
    } else if (e.code === 'KeyR') {
        window.location = '/shorts/'
    } else if (e.code === 'KeyT') {
        window.location = '/paste/'
    } else if (e.code === 'KeyY') {
        window.location = '/admin/settings/sitesettings/1/change/'
    } else if (e.code === 'KeyX') {
        window.location = '/settings/sharex/'
    }
})
