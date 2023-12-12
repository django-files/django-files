// JS for Context Menu
// TODO: Review EVERYTHING in this file

// Expire - Context Menu Click
$('.ctx-expire').on('click', setExpireClick)

// Expire - Form Submit
$('#set-expr-form').on('submit', function (event) {
    console.log('#set-expr-form.submit')
    event.preventDefault()
    const data = genData($('#set-expr-form').serializeArray(), 'set-expr-file')
    console.log(data)
    socket.send(JSON.stringify(data))
    $('#setFileExprModal').modal('hide')
})

// Expire - Focus Input
$('#setFileExprModal').on('shown.bs.modal', function () {
    $('#expr').trigger('focus').select()
})

// Private - Toggle Click
$('.ctx-private').on('click', togglePrivateClick)

// Password - Set Password Context Menu Button
$('.ctx-password').on('click', setPasswordClick)

// TODO: Review and Cleanup all other Password handlers

// Password - Set Password Form Submission
$('#set-password-form').on('submit', (event) => {
    console.log('#set-password-form.submit', event)
    event.preventDefault()
    // console.log('this', this)
    const data = genData(
        $('#set-password-form').serializeArray(),
        'set-password-file'
    )
    // const formData = new FormData(event.target)
    // console.log('formData:', formData)
    // console.log('formData.password:', formData.get('password'))
    // const data = {
    //     method: 'set-password-file',
    //     pk: formData.get('pk').toString(),
    //     password: formData.get('password').toString(),
    // }
    console.log(data)
    console.log(`data.pk: ${data.pk}`)
    socket.send(JSON.stringify(data))
    $(`#ctx-menu-${data.pk} input[name=current-file-password]`).val(
        data.password
    )
    $('#setFilePasswordModal').modal('hide')
})

// Password - Misc
$('#unMaskPassword').on('click', function () {
    // TODO: This needs a cookie to work properly
    const password = $('#password')
    const type = password[0].type === 'password' ? 'text' : 'password'
    password.prop('type', type)
})

// Password - Misc
$('#copyPassword').on('click', async function () {
    // TODO: Use clipboardjs vs a custom function
    await navigator.clipboard.writeText($('#password').val())
    show_toast('Password copied!', 'info', '15000')
})

// Password - Misc
$('#generatePassword').on('click', async function () {
    // TODO: Cleanup this Listener
    const chars =
        '0123456789abcdefghijklmnopqrstuvwxyz!+()ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    const pwordLength = 15
    let password = ''

    const array = new Uint32Array(chars.length)
    window.crypto.getRandomValues(array)

    for (let i = 0; i < pwordLength; i++) {
        password += chars[array[i] % chars.length]
    }
    $('#password').val(password)
    await navigator.clipboard.writeText(password)
    show_toast('Password generated and copied!', 'info', '15000')
})

// Password - Misc
$('#setFilePasswordModal').on('shown.bs.modal', function () {
    $('#password').focus().select()
})

// Delete - Delete File Context Menu Button
$('.ctx-delete').on('click', deleteFileClick)

// Delete -  Delete File Confirm Button
$('#confirmDeleteFileBtn').on('click', function () {
    const pk = $(this).data('pk')
    console.log(`#confirmDeleteFileBtn.click: pk: ${pk}`)
    socket.send(JSON.stringify({ method: 'delete-file', pk: pk }))
    if (window.location.pathname.startsWith('/u/')) {
        window.location.replace('/#files')
    } else {
        $('#deleteFileModal').modal('hide')
    }
})

// ---------- SOCKET HANDLERS ----------

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

// Event Listeners

// Set Expire Listener
function setExpireClick() {
    const pk = $(this).parent().parent().parent().data('pk')
    console.log(`setExpireClick: ${pk}`)
    $('#set-expr-form input[name=pk]').val(pk)
    const expireText = $(`#file-${pk} .expire-value`).text()
    console.log(`expireText: ${expireText}`)
    $('#set-expr-form input[name=expr]').val(expireText)
    const expireValue = expireText === 'Never' ? '' : expireText
    console.log(`expireValue: ${expireValue}`)
    $('#expr').val(expireValue)
    $('#setFileExprModal').modal('show')
}

// Toggle Private Listener
function togglePrivateClick() {
    const pk = $(this).parent().parent().parent().data('pk')
    console.log(`togglePrivateClick: ${pk}`)
    socket.send(JSON.stringify({ method: 'toggle-private-file', pk: pk }))
}

// Set Password Listener
function setPasswordClick() {
    const pk = $(this).parent().parent().parent().data('pk')
    console.log(`setPasswordClick: ${pk}`)
    $('#setFilePasswordModal input[name=pk]').val(pk)
    const input = $(`#ctx-menu-${pk} input[name=current-file-password]`)
    console.log('input:', input)
    const password = input.val()
    console.log(`password: ${password}`)
    $('#password').val(input.val())
    $('#setFilePasswordModal').modal('show')
}

// Delete Click Listener
function deleteFileClick() {
    const pk = $(this).parent().parent().parent().data('pk')
    console.log(`deleteFileClick: ${pk}`)
    $('#confirmDeleteFileBtn').data('pk', pk)
    $('#deleteFileModal').modal('show')
}

// Socket Handlers

function handle_set_expiration(data) {
    // Expire Socket Handler
    // TODO: title does not seem to live update using .attr method
    // TODO: clipboard-text does not seem to live update using .data method
    console.log('handle_set_expiration')
    // console.log(data)
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
    // Private Socket Handler
    console.log('handle_private_toggle')
    // console.log(data)
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
    // Password Socket Handler
    console.log(`handle_password_set`)
    // console.log(data)
    const table_icon = $(`#file-${data.id} .passwordStatus`)
    const preview_icon = $(`#passwordStatus`)
    // console.log(table_icon)
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
 *
 * @param {Array} serializeArray
 * @param {String} method
 * @return {Object}
 */
function genData(serializeArray, method) {
    // Convert .serializeArray() to Object (key: value)
    const data = { method: method }
    for (const element of serializeArray) {
        data[element['name']] = element['value']
    }
    return data
}
