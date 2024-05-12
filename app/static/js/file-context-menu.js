// JS for Context Menu

console.debug('LOADING: file-context-menu.js')

const fileExpireModal = $('#fileExpireModal')
const filePasswordModal = $('#filePasswordModal')
const fileDeleteModal = $('#fileDeleteModal')

$('.ctx-expire').on('click', cxtSetExpire)
$('.ctx-private').on('click', ctxSetPrivate)
$('.ctx-password').on('click', ctxSetPassword)
$('.ctx-delete').on('click', ctxDeleteFile)

socket?.addEventListener('message', function (event) {
    // console.log('socket.message: file-context-menu.js:', event)
    const data = JSON.parse(event.data)
    if (data.event === 'set-expr-file') {
        messageExpire(data)
    } else if (data.event === 'toggle-private-file') {
        messagePrivate(data)
    } else if (data.event === 'set-password-file') {
        messagePassword(data)
    } else if (data.event === 'file-delete') {
        messageDelete(data)
    }
})

// Expire Form

fileExpireModal.on('shown.bs.modal', function (event) {
    console.log('fileExpireModal shown.bs.modal:', event)
    $(this).find('input').trigger('focus').trigger('select')
})

$('#modal-expire-form').on('submit', function (event) {
    console.log('#modal-expire-form submit:', event)
    event.preventDefault()
    // const data = {
    //     method: 'set-expr-file',
    //     pk: $(this).find('input[name=pk]').val(),
    //     expr: $(this).find('input[name=expr]').val().trim(),
    // }
    const data = genData($(this), 'set-expr-file')
    console.log('data:', data)
    socket.send(JSON.stringify(data))
    fileExpireModal.modal('hide')
})

// Password Form
// TODO: Cleanup Password Forms

filePasswordModal.on('shown.bs.modal', function (event) {
    console.log('filePasswordModal shown.bs.modal:', event)
    $(this).find('input').trigger('focus').trigger('select')
})

$('#modal-password-form').on('submit', function (event) {
    console.log('#modal-password-form submit:', event)
    event.preventDefault()
    // const data = {
    //     method: 'set-password-file',
    //     pk: $(this).find('input[name=pk]').val(),
    //     password: $(this).find('input[name=password]').val().trim(),
    // }
    const data = genData($(this), 'set-password-file')
    console.log('data:', data)
    socket.send(JSON.stringify(data))
    $(`#ctx-menu-${data.pk} input[name=current-file-password]`).val(
        data.password
    )
    filePasswordModal.modal('hide')
})

$('#password-unmask').on('click', function (event) {
    console.log('#password-unmask click:', event)
    const input = $('#password')
    const type = input.attr('type') === 'password' ? 'text' : 'password'
    input.prop('type', type)
})

$('#password-copy').on('click', async function (event) {
    console.log('#password-copy click:', event)
    await navigator.clipboard.writeText($('#password').val())
    show_toast('Password copied!', 'info')
})

$('#password-generate').on('click', async function (event) {
    console.log('#password-generate click:', event)
    const password = genRand(12)
    $('#password').val(password)
    await navigator.clipboard.writeText(password)
    show_toast('Password generated and copied!', 'info')
})

// Delete File Form

$('#confirm-delete').on('click', function (event) {
    // TODO: Handle IF/ELSE Better
    const pk = $(this).data('pk')
    console.log(`#confirm-delete click pk: ${pk}`, event)
    socket.send(JSON.stringify({ method: 'delete-file', pk: pk }))
    if (window.location.pathname.startsWith('/u/')) {
        window.location.replace('/#files')
    } else {
        fileDeleteModal.modal('hide')
    }
})

// Event Listeners

function cxtSetExpire(event) {
    const pk = getPrimaryKey(event)
    console.log(`getPrimaryKey pk: ${pk}`, event)
    fileExpireModal.find('input[name=pk]').val(pk)
    const expire = $(`#file-${pk} .expire-value`).text().trim()
    console.log(`expire: ${expire}`)
    const expireValue = expire === 'Never' ? '' : expire
    console.log(`expireInput: ${expireValue}`)
    $('#expr').val(expireValue)
    fileExpireModal.modal('show')
}

function ctxSetPrivate(event) {
    const pk = getPrimaryKey(event)
    console.log(`ctxSetPrivate pk: ${pk}`, event)
    socket.send(JSON.stringify({ method: 'toggle-private-file', pk: pk }))
}

function ctxSetPassword(event) {
    const pk = getPrimaryKey(event)
    console.log(`ctxSetPassword pk: ${pk}`, event)
    filePasswordModal.find('input[name=pk]').val(pk)
    const input = $(`#ctx-menu-${pk} input[name=current-file-password]`)
    // console.log('input:', input)
    const password = input.val().toString().trim()
    console.log(`password: ${password}`)
    // $('#password').val(input.val())
    filePasswordModal.find('input[name=password]').val(password)
    filePasswordModal.modal('show')
}

function ctxDeleteFile(event) {
    const pk = getPrimaryKey(event)
    console.log(`ctxDeleteFile pk: ${pk}`, event)
    $('#confirm-delete').data('pk', pk)
    fileDeleteModal.modal('show')
}

function getPrimaryKey(event) {
    const menu = event.target.closest('div')
    let pk = menu?.dataset?.id
    if (!pk) {
        console.warn('OLD PK QUERY USED')
        pk = $(this).parent().parent().parent().data('pk')
    }
    return pk
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
}

/**
 * Generate Random String at length
 * @param {Number} length
 * @return {String}
 */
function genRand(length) {
    const chars =
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    let result = ''
    let counter = 0
    while (counter < length) {
        const rand = Math.floor(Math.random() * chars.length)
        result += chars.charAt(rand)
        counter += 1
    }
    return result
}

/**
 * Convert Form Object to Object
 * @param {jQuery} form $(this) from on submit event
 * @param {String} method The method key value
 * @return {Object}
 */
function genData(form, method) {
    const data = { method: method }
    for (const element of form.serializeArray()) {
        data[element['name']] = element['value']
    }
    return data
}
