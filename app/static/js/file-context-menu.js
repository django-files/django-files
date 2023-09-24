$(document).ready(function () {
    socket.addEventListener('message', function (event) {
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

    // ---------- EXPIRE ----------

    // Expire - Context Menu Click
    $('.ctx-set-expire-btn').click(function () {
        const pk = $(this).parent().parent().data('pk')
        console.log(`.ctx-set-expire-btn: pk: ${pk}`)
        $('#set-expr-form input[name=pk]').val(pk)
        const expireText = $(`#file-${pk} .expire-value`).text()
        console.log(`expireText: ${expireText}`)
        $('#set-expr-form input[name=expr]').val(expireText)
        const expireValue = expireText === 'Never' ? '' : expireText
        console.log(`expireValue: ${expireValue}`)
        $('#expr').val(expireValue)
        $('#setFileExprModal').modal('show')
    })

    // Expire - Form Submit
    $('#set-expr-form').submit(function (event) {
        event.preventDefault()
        console.log('#set-expr-form.submit')
        const data = objectifyForm($('#set-expr-form').serializeArray())
        data.method = 'set-expr-file'
        console.log(data)
        socket.send(JSON.stringify(data))
        $('#setFileExprModal').modal('hide')
    })

    // Expire - Focus Input
    $('#setFileExprModal').on('shown.bs.modal', function () {
        $('#expr').trigger('focus').select()
    })

    // ---------- PRIVATE ----------

    // Private - Toggle Click
    $('.ctx-toggle-private-btn').click(function (event) {
        event.preventDefault()
        let pk = $(this).data('pk')
        console.log(`.ctx-toggle-private-btn: pk: ${pk}`)
        socket.send(JSON.stringify({ method: 'toggle-private-file', pk: pk }))
    })

    // ---------- PASSWORD ----------

    // Password - Set Password Context Menu Button
    $('.ctx-set-password-btn').click(function () {
        const pk = $(this).data('pk')
        console.log(`.ctx-set-password-btn: pk: ${pk}`)
        $('#setFilePasswordModal input[name=pk]').val(pk)
        const currentPassInput = $(
            `#ctx-menu-${pk} input[name=current-file-password]`
        )
        console.log(`currentInput: ${currentPassInput}`)
        const passwordText = currentPassInput.val()
        console.log(`passwordText: ${passwordText}`)
        $('#password').val(passwordText)
        $('#setFilePasswordModal').modal('show')
    })

    // TODO: Review and Cleanup all other Password handlers

    // Password - Set Password Form Submission
    $('#set-password-form').submit(function (event) {
        event.preventDefault()
        console.log('#set-password-form.submit')
        const data = objectifyForm($(this).serializeArray())
        console.log(`data.password: ${data.password}`)
        data.method = 'set-password-file'
        console.log(data)
        socket.send(JSON.stringify(data))
        $(`#ctx-menu-${data.pk} input[name=current-file-password]`).val(
            data.password
        )
        $('#setFilePasswordModal').modal('hide')
    })

    // Password - Misc
    $('#unMaskPassword').click(function () {
        const password = $('#password')
        console.log(`#unMaskPassword: password: ${password}`)
        const type = password.type === 'password' ? 'text' : 'password'
        password.prop('type', type)
    })

    // Password - Misc
    // TODO: Why do we need a custom function for this vs clipboardjs
    $('#copyPassword').click(async function () {
        await navigator.clipboard.writeText($('#password').val())
        show_toast('Password copied!', 'info', '15000')
    })

    // Password - Misc
    $('#generatePassword').click(async function () {
        // TODO: Cleanup this Listener
        console.log('#generatePassword.click')
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

    // ---------- DELETE ----------

    // Delete - Delete File Context Menu Button
    $('.ctx-delete-btn').click(deleteFileClick)

    // Delete -  Delete File Confirm Button
    $('#confirmDeleteFileBtn').click(function () {
        const pk = $(this).data('pk')
        console.log(`#confirmDeleteFileBtn: pk: ${pk}`)
        socket.send(JSON.stringify({ method: 'delete-file', pk: pk }))
        $('#deleteFileModal').modal('hide')
    })
})

// Expire Socket Handler
function handle_set_expiration(data) {
    console.log('handle_set_expiration')
    console.log(data)
    const expireTableText = $(`#file-${data.id} .expire-value`)
    const expirePreviewIcon = $('#expire-status-icon')
    console.log(`data.expr: ${data.expr}`)
    if (data.expr) {
        expireTableText.text(data.expr)
        // TODO: title does not seem to live update using .attr method
        expirePreviewIcon.attr('title', `File Expires in ${data.expr}`).show()
        show_toast(`${data.name} - Expire set to: ${data.expr}`, 'success')
    } else {
        expireTableText.text('Never')
        expirePreviewIcon.attr('title', 'No Expiration').hide()
        show_toast(`${data.name} - Cleared Expiration.`, 'success')
    }
}

// Private Socket Handler
function handle_private_toggle(data) {
    // TODO: Re-write this function and selectors
    // TODO: Use Logical Names for Selectors
    console.log('handle_private_toggle')
    console.log(data)
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

// Password Socket Handler
function handle_password_set(data) {
    console.log(`handle_password_set`)
    console.log(data)
    // $(`#file-${data.id} .passwordStatus`).toggle()
    const table_icon = $(`#file-${data.id} .passwordStatus`)
    console.log(table_icon)
    if (data.password) {
        table_icon.show()
        show_toast(`Password set for ${data.name}`, 'success')
    } else {
        table_icon.hide()
        show_toast(`Password unset for ${data.name}`, 'success')
    }
    $('#setFilePasswordModal').modal('hide')
}

// Extras

function objectifyForm(formArray) {
    // Convert .serializeArray() to Object (key: value)
    let returnArray = {}
    for (const element of formArray) {
        returnArray[element['name']] = element['value']
    }
    return returnArray
}
