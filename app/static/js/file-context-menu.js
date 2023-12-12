// JS for Context Menu

// Context Menu Listeners

$('.ctx-expire').on('click', cxtSetExpire)
$('.ctx-private').on('click', ctxSetPrivate)
$('.ctx-password').on('click', ctxSetPassword)
$('.ctx-delete').on('click', ctxDeleteFile)

// Expire Form

$('#set-expr-form').on('submit', (event) => {
    console.log('#set-expr-form submit:', event)
    event.preventDefault()
    const data = genData($('#set-expr-form').serializeArray(), 'set-expr-file')
    console.log('data:', data)
    socket.send(JSON.stringify(data))
    $('#setFileExprModal').modal('hide')
})

$('#setFileExprModal').on('shown.bs.modal', () => {
    $('#expr').trigger('focus').trigger('select')
})

// Password Form
// TODO: Cleanup Password Forms

$('#set-password-form').on('submit', (event) => {
    console.log('#set-password form.submit:', event)
    event.preventDefault()
    const data = genData(
        $('#set-password-form').serializeArray(),
        'set-password-file'
    )
    console.log('data:', data)
    socket.send(JSON.stringify(data))
    $(`#ctx-menu-${data.pk} input[name=current-file-password]`).val(
        data.password
    )
    $('#setFilePasswordModal').modal('hide')
})

$('#unMaskPassword').on('click', () => {
    // TODO: This needs a cookie to work properly
    console.log('#unMaskPassword click:')
    const password = $('#password')
    const type = password.attr('type') === 'password' ? 'text' : 'password'
    password.prop('type', type)
})

$('#copyPassword').on('click', async () => {
    await navigator.clipboard.writeText($('#password').val())
    show_toast('Password copied!', 'info', '15000')
})

$('#generatePassword').on('click', async () => {
    const password = genRand(12)
    $('#password').val(password)
    await navigator.clipboard.writeText(password)
    show_toast('Password generated and copied!', 'info', '15000')
})

$('#setFilePasswordModal').on('shown.bs.modal', () => {
    $('#password').trigger('focus').trigger('select')
})

// Delete File Form

$('#confirmDeleteFileBtn').on('click', () => {
    // TODO: Handle ELSE Better
    const pk = $(this).data('pk')
    console.log(`#confirmDeleteFileBtn.click: pk: ${pk}`)
    socket.send(JSON.stringify({ method: 'delete-file', pk: pk }))
    if (window.location.pathname.startsWith('/u/')) {
        window.location.replace('/#files')
    } else {
        $('#deleteFileModal').modal('hide')
    }
})

// Event Listeners

function cxtSetExpire() {
    const pk = $(this).parent().parent().parent().data('pk')
    console.log(`cxtSetExpire pk: ${pk}`, this)
    $('#set-expr-form input[name=pk]').val(pk)
    const expire = $(`#file-${pk} .expire-value`).text().trim()
    console.log(`expire: ${expire}`)
    $('#set-expr-form input[name=expr]').val(expire)
    const expireValue = expire === 'Never' ? '' : expire
    console.log(`expireValue: ${expireValue}`)
    $('#expr').val(expireValue)
    $('#setFileExprModal').modal('show')
}

function ctxSetPrivate() {
    const pk = $(this).parent().parent().parent().data('pk')
    console.log(`ctxSetPrivate pk: ${pk}`, this)
    socket.send(JSON.stringify({ method: 'toggle-private-file', pk: pk }))
}

function ctxSetPassword() {
    const pk = $(this).parent().parent().parent().data('pk')
    console.log(`ctxSetPassword pk: ${pk}`, this)
    $('#setFilePasswordModal input[name=pk]').val(pk)
    const input = $(`#ctx-menu-${pk} input[name=current-file-password]`)
    // console.log('input:', input)
    const password = input.val().toString().trim()
    console.log(`password: ${password}`)
    $('#password').val(input.val())
    $('#setFilePasswordModal').modal('show')
}

function ctxDeleteFile() {
    const pk = $(this).parent().parent().parent().data('pk')
    console.log(`ctxDeleteFile pk: ${pk}`, this)
    $('#confirmDeleteFileBtn').data('pk', pk)
    $('#deleteFileModal').modal('show')
}

// Socket Handlers

socket?.addEventListener('message', (event) => {
    console.log('socket: file-context-menu.js:', event)
    const data = JSON.parse(event.data)
    if (data.event === 'set-expr-file') {
        // Expire
        handle_set_expiration(data)
    } else if (data.event === 'toggle-private-file') {
        // Private
        handle_private_toggle(data)
    } else if (data.event === 'set-password-file') {
        // Password
        handle_password_set(data)
    }
})

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
    console.log('handle_password_setL', data)
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
    $('#setFilePasswordModal').modal('hide')
}

// Misc

/**
 * Convert serializeArray to Object
 * @param {Array} serializeArray
 * @param {String} method
 * @return {Object}
 */
function genData(serializeArray, method) {
    const data = { method: method }
    for (const element of serializeArray) {
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
        '0123456789abcdefghijklmnopqrstuvwxyz!+()ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    let password = ''
    const array = new Uint32Array(chars.length)
    window.crypto.getRandomValues(array)

    for (let i = 0; i < length; i++) {
        password += chars[array[i] % chars.length]
    }
    return password
}
