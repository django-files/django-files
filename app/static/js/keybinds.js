// JS for Keyboard Shortcuts

let keysPressed = {}
window.onblur = function () {
    keysPressed = {}
}
window.addEventListener('keydown', handleKeybinds)
document.addEventListener('keyup', (event) => {
    delete keysPressed[event.key]
})

/**
 * Keyboard keydown Callback
 * @function handleKeybinds
 * @param {KeyboardEvent} event
 */
function handleKeybinds(event) {
    // console.log('handleKeybinds:', event)
    const formElements = ['INPUT', 'TEXTAREA', 'SELECT', 'OPTION']
    if (!formElements.includes(event.target.tagName)) {
        keysPressed[event.key] = true
        if (checkKey(event, ['KeyA'])) {
            window.location = '/uppy/'
        } else if (checkKey(event, ['KeyS'])) {
            window.location = '/settings/user/'
        } else if (checkKey(event, ['KeyD'])) {
            window.location = '/settings/site/'
        } else if (checkKey(event, ['KeyF'])) {
            window.location = '/files/'
        } else if (checkKey(event, ['KeyG'])) {
            window.location = '/gallery/'
        } else if (checkKey(event, ['KeyH'])) {
            window.location = '/'
        } else if (checkKey(event, ['KeyR'])) {
            window.location = '/shorts/'
        } else if (checkKey(event, ['KeyT'])) {
            window.location = '/paste/'
        } else if (checkKey(event, ['KeyY'])) {
            window.location = '/admin/settings/sitesettings/1/change/'
        } else if (checkKey(event, ['KeyX'])) {
            window.location = '/settings/sharex/'
        } else if (checkKey(event, ['KeyZ', 'KeyK'])) {
            $('#keybinds-modal').modal('toggle')
        }
    }
}

/**
 * Check Key Down Combination
 * @function checkKey
 * @param {KeyboardEvent} event
 * @param {Array} keys
 * @return {Boolean}
 */
function checkKey(event, keys) {
    const ctrlKeys = ['Control', 'Alt', 'Shift', 'Meta']
    let hasCtrlKey = false
    ctrlKeys.forEach(function (key) {
        if (keysPressed[key]) {
            hasCtrlKey = true
        }
    })
    if (hasCtrlKey) {
        return false
    }
    return !!keys.includes(event.code)
}
