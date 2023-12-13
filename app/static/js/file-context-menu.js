// JS for Context Menu

const fileExpireModal = $('#fileExpireModal')
const filePasswordModal = $('#filePasswordModal')
const fileDeleteModal = $('#fileDeleteModal')

$('.ctx-expire').on('click', cxtSetExpire)
$('.ctx-private').on('click', ctxSetPrivate)
$('.ctx-password').on('click', ctxSetPassword)
$('.ctx-delete').on('click', ctxDeleteFile)

socket?.addEventListener('message', function (event) {
    // console.log('socket: file-context-menu.js:', event)
    const data = JSON.parse(event.data)
    if (data.event === 'set-expr-file') {
        handle_set_expiration(data)
    } else if (data.event === 'toggle-private-file') {
        handle_private_toggle(data)
    } else if (data.event === 'set-password-file') {
        handle_password_set(data)
    }
})

// Expire Form

fileExpireModal.on('shown.bs.modal', function (event) {
    console.log('fileExpireModal shown.bs.modal:', event, this)
    $(this).find('input').trigger('focus').trigger('select')
})

$('#modal-expire-form').on('submit', function (event) {
    console.log('#modal-expire-form submit:', event, this)
    event.preventDefault()
    const data = genData($(this), 'set-expr-file')
    console.log('data:', data)
    socket.send(JSON.stringify(data))
    fileExpireModal.modal('hide')
})

// Password Form
// TODO: Cleanup Password Forms

filePasswordModal.on('shown.bs.modal', function (event) {
    console.log('filePasswordModal shown.bs.modal:', event, this)
    $(this).find('input').trigger('focus').trigger('select')
})

$('#modal-password-form').on('submit', function (event) {
    console.log('#modal-password-form submit:', event, this)
    event.preventDefault()
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
    show_toast('Password copied!', 'info', '15000')
})

$('#password-generate').on('click', async function (event) {
    console.log('#password-generate click:', event)
    const password = genRand(12)
    $('#password').val(password)
    await navigator.clipboard.writeText(password)
    show_toast('Password generated and copied!', 'info', '15000')
})

// Delete File Form

$('#confirm-delete').on('click', function (event) {
    // TODO: Handle IF/ELSE Better
    const pk = $(this).data('pk')
    console.log(`#confirm-delete click: pk: ${pk}`, event, this)
    socket.send(JSON.stringify({ method: 'delete-file', pk: pk }))
    if (window.location.pathname.startsWith('/u/')) {
        window.location.replace('/#files')
    } else {
        fileDeleteModal.modal('hide')
    }
})

// Event Listeners

function cxtSetExpire() {
    const pk = $(this).parent().parent().parent().data('pk')
    console.log(`cxtSetExpire pk: ${pk}`, this)
    fileExpireModal.find('input[name=pk]').val(pk)
    const expire = $(`#file-${pk} .expire-value`).text().trim()
    console.log(`expire: ${expire}`)
    const expireValue = expire === 'Never' ? '' : expire
    console.log(`expireInput: ${expireValue}`)
    $('#expr').val(expireValue)
    fileExpireModal.modal('show')
}

function ctxSetPrivate() {
    const pk = $(this).parent().parent().parent().data('pk')
    console.log(`ctxSetPrivate pk: ${pk}`, this)
    socket.send(JSON.stringify({ method: 'toggle-private-file', pk: pk }))
}

function ctxSetPassword() {
    const pk = $(this).parent().parent().parent().data('pk')
    console.log(`ctxSetPassword pk: ${pk}`, this)
    filePasswordModal.find('input[name=pk]').val(pk)
    const input = $(`#ctx-menu-${pk} input[name=current-file-password]`)
    // console.log('input:', input)
    const password = input.val().toString().trim()
    console.log(`password: ${password}`)
    $('#password').val(input.val())
    filePasswordModal.modal('show')
}

function ctxDeleteFile() {
    const pk = $(this).parent().parent().parent().data('pk')
    console.log(`ctxDeleteFile pk: ${pk}`, this)
    $('#confirm-delete').data('pk', pk)
    fileDeleteModal.modal('show')
}

// Socket Handlers

function handle_set_expiration(data) {
    // TODO: title does not seem to live update using .attr method
    // TODO: clipboard-text does not seem to live update using .data method
    console.log('handle_set_expiration', data)
    const expireTableText = $(`#file-${data.id} .expire-value`)
    const expirePreviewIcon = $('#expire-status-icon')
    if (data.expr) {
        expireTableText.text(data.expr).data('clipboard-text', data.expr)
        expirePreviewIcon.attr('title', `File Expires in ${data.expr}`).show()
        show_toast(`${data.name} - Expire set to: ${data.expr}`, 'success')
    } else {
        expireTableText.text('Never').data('clipboard-text', 'Never')
        expirePreviewIcon.attr('title', 'No Expiration').hide()
        show_toast(`${data.name} - Cleared Expiration.`, 'success')
    }
}

function handle_private_toggle(data) {
    console.log('handle_private_toggle', data)
    const ctx_text = $(`#ctx-menu-${data.id} .privateText`)
    const ctx_icon = $(`#ctx-menu-${data.id} .privateDropdownIcon`)
    const table_icon = $(`#file-${data.id} .privateStatus`)
    const preview_icon = $(`#privateStatus`)
    if (data.private) {
        console.log('Making PRIVATE')
        table_icon.show()
        preview_icon.show()
        ctx_text.text('Make Public')
        ctx_icon.removeClass('fa-lock').addClass('fa-lock-open')
        show_toast(`File ${data.name} set to private.`, 'success')
    } else {
        console.log('Making PUBLIC')
        table_icon.hide()
        preview_icon.hide()
        ctx_text.text('Make Private')
        ctx_icon.removeClass('fa-lock-open').addClass('fa-lock')
        show_toast(`File ${data.name} set to public.`, 'success')
    }
}

function handle_password_set(data) {
    console.log('handle_password_set', data)
    const table_icon = $(`#file-${data.id} .passwordStatus`)
    const preview_icon = $(`#passwordStatus`)
    if (data.password) {
        table_icon.show()
        preview_icon.show()
        show_toast(`Password set for ${data.name}`, 'success')
    } else {
        table_icon.hide()
        preview_icon.hide()
        show_toast(`Password unset for ${data.name}`, 'success')
    }
    filePasswordModal.modal('hide')
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
