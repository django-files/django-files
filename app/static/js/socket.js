// JS for Web Sockets
// TODO: Look Into Moving Everything Here for Auto Reconnect

let disconnected = false
let socket
let ws

console.log('Connecting to WebSocket...')
wsConnect()

async function wsConnect() {
    if (ws) {
        console.warn('Closing Existing WebSocket Connection!')
        ws.close()
    }
    const toast = bootstrap.Toast.getOrCreateInstance($('#disconnected-toast'))
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    socket = new WebSocket(`${protocol}//${window.location.host}/ws/home/`)
    socket.onopen = function (event) {
        console.log('WebSocket Connected.', event)
        disconnected = false
        if (toast.isShown()) {
            $('#disconnected-toast-title')
                .removeClass('text-danger')
                .addClass('text-warning')
                .text('Connected')
            toast.hide()
        }
    }
    // socket.onmessage = function (event) {
    //     console.log('socket.onmessage:', event)
    // }
    socket.onclose = function (event) {
        if (![1000, 1001].includes(event.code)) {
            if (!disconnected) {
                console.warn('WebSocket Disconnected!', event)
            }
            if (!toast.isShown()) {
                setTimeout(function () {
                    disconnected = true
                    $('#disconnected-toast-title')
                        .removeClass('text-warning')
                        .addClass('text-danger')
                        .text('Reconnecting...')
                    toast.show()
                }, 2 * 1000)
            }
        }
        setTimeout(function () {
            wsConnect()
        }, 10 * 1000)
    }
    socket.onerror = function (event) {
        if (!disconnected) {
            console.error('WebSocket Error:', event)
        }
    }
    initListener()
}

// File Events

async function initListener() {
    socket?.addEventListener('message', function (event) {
        // console.log('socket.message: files.js:', event)
        let data = JSON.parse(event.data)
        console.log(event)
        if (data.event === 'file-new') {
            newFile(data)
        } else if (data.event === 'set-expr-file') {
            messageExpire(data)
        } else if (data.event === 'toggle-private-file') {
            messagePrivate(data)
        } else if (data.event === 'set-password-file') {
            messagePassword(data)
        } else if (data.event === 'file-delete') {
            messageDelete(data)
        } else if (data.event === 'message') {
            console.log(`data.message: ${data.message}`)
            const bsClass = data.bsClass || 'info'
            const delay = data.delay || '6000'
            show_toast(data.message, bsClass, delay)
        }
    })
}

// Socket Handlers

function messageExpire(data) {
    console.log('messageExpire:', data)
    const expireText = $(`#file-${data.id} .expire-value`)
    const expireIcon = $(`#file-${data.id} .expire-icon`)
    if (data.expr) {
        expireText.text(data.expr).data('clipboard-text', data.expr)
        expireIcon.attr('title', `File Expires in ${data.expr}`).show()
        show_toast(`${data.name} - Expire set to: ${data.expr}`, 'success')
    } else {
        expireText.text('Never').data('clipboard-text', 'Never')
        expireIcon.attr('title', 'No Expiration').hide()
        show_toast(`${data.name} - Cleared Expiration.`, 'success')
    }
}

function messagePrivate(data) {
    // TODO: Cleanup Selectors
    console.log('messagePrivate:', data)
    const privateStatus = $(`#file-${data.id} .privateStatus`)
    const previewIcon = $(`#previewIcon`)
    const ctxPrivateText = $(`#ctx-menu-${data.id} .privateText`)
    const ctxPrivateIcon = $(`#ctx-menu-${data.id} .privateIcon`)
    if (data.private) {
        privateStatus.show()
        previewIcon.show()
        ctxPrivateText.text('Make Public')
        ctxPrivateIcon.removeClass('fa-lock').addClass('fa-lock-open')
        show_toast(`File ${data.name} set to private.`, 'success')
    } else {
        privateStatus.hide()
        previewIcon.hide()
        ctxPrivateText.text('Make Private')
        ctxPrivateIcon.removeClass('fa-lock-open').addClass('fa-lock')
        show_toast(`File ${data.name} set to public.`, 'success')
    }
}

function messagePassword(data) {
    console.log('messagePassword', data)
    const passwordStatus = $(`#file-${data.id} .passwordStatus`)
    if (data.password) {
        passwordStatus.show()
        show_toast(`Password set for ${data.name}`, 'success')
    } else {
        passwordStatus.hide()
        show_toast(`Password unset for ${data.name}`, 'success')
    }
    filePasswordModal.modal('hide')
}

function messageDelete(data) {
    $(`#file-${data.pk}`).remove()
    show_toast(`${data.name} deleted by ${data.user}.`)
}

function newFile(data) {
    $.get(`/api/file/${data.pk}`, function (response) {
        console.log(response)
        addDTRow(response)
        show_toast(`${response.name} added.`)
    })
}
