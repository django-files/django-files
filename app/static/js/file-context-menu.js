$(document).ready(function () {
    socket.addEventListener('message', function (event) {
        const data = JSON.parse(event.data)
        if (data.event === 'toggle-private-file') {
            handle_private_toggle(data)
        } else if (data.event === 'set-expr-file') {
            handle_set_expiration(data)
        } else if (data.event === 'set-password-file') {
            handle_password_set(data)
        }
    })

    // TODO: Stop Doing This
    // let pk

    $('.delete-file-btn').click(function () {
        const pk = $(this).data('pk')
        console.log(`Delete Button: pk: ${pk}`)
        $('#confirmDeleteFileBtn').data('pk', pk)
        $('#deleteFileModal').modal('show')
    })

    // Handle delete click confirmations
    $('#confirmDeleteFileBtn').click(function () {
        const pk = $(this).data('pk')
        console.log(`Confirm Delete: pk: ${pk}`)
        socket.send(JSON.stringify({ method: 'delete-file', pk: pk }))
        $('#deleteFileModal').modal('hide')
    })

    $('.set-password-file-btn').click(function () {
        const pk = $(this).data('pk')
        console.log(`Set File Password Button: ${pk}`)
        $('#confirm-set-password-hook-btn').data('pk', pk)
        const setFilePasswordModal = $('#setFilePasswordModal')
        // TODO: Use Actual Selectors
        const passwordText = $(`#file-${pk}-dropdown`)
            .find('.file-password-value')
            .val()
        // TODO: Use Actual Selectors
        setFilePasswordModal.find('#password').val(passwordText)
        setFilePasswordModal.show()
    })

    // Handle set password click confirmations
    $('#confirm-set-password-hook-btn').click(function (event) {
        event.preventDefault()
        // TODO: pk is not defined here
        let formData = new $('#set-password-form').serializeArray()
        socket.send(
            JSON.stringify({
                method: 'set-password-file',
                pk: pk,
                password: formData[0].value,
            })
        )
        // TODO: Use Actual Selectors
        $(`#file-${pk}`).find('.file-password-value').val(formData[0].value)
    })

    $('.toggle-private-btn').click(function (event) {
        event.preventDefault()
        let pk = $(this).data('pk')
        console.log(`Toggle Private Button: ${pk}`)
        socket.send(JSON.stringify({ method: 'toggle-private-file', pk: pk }))
    })

    $('#unMaskPassword').click(function () {
        const password = $('#password')
        const type = password.type === 'password' ? 'text' : 'password'
        password.prop('type', type)
    })

    $('#copyPassword').click(async function () {
        await navigator.clipboard.writeText($('#password').val())
        show_toast('Password copied!', 'info', '15000')
    })

    $('#generatePassword').click(async function () {
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

    $('#setFilePasswordModal').on('shown.bs.modal', function () {
        $('#password').focus()
    })

    $('.set-expr-btn').click(function () {
        const pk = $(this).data('pk')
        $('#confirmFileExprBtn').data('pk', pk)
        // TODO: Use Actual Selectors
        let expireText = $(`#file-${pk}`).find('#expireText')
        let expireModal = $('#setFileExprModal')
        if (expireText.length > 0) {
            let value = expireText.html()
            if (value === 'Never') {
                value = ''
            }
            // TODO: Use Actual Selectors
            expireModal.find('#expr').val(value)
        }
        expireModal.modal('show')
    })

    $('#setFileExprModal').on('shown.bs.modal', function () {
        $('#expr').trigger('focus')
    })

    $('#set-expr-form').submit(function (event) {
        event.preventDefault()
        // TODO: pk is not defined here
        let formData = new $('#set-expr-form').serializeArray()
        socket.send(
            JSON.stringify({
                method: 'set-expr-file',
                pk: pk,
                expr: formData[0].value,
            })
        )
        $('#setFileExprModal').modal('hide')
    })
})

function handle_password_set(data) {
    // TODO: Use Actual Selectors
    const password_status_icon = $(`#file-${data.pk}`).find('.passwordStatus')
    if (data.password) {
        password_status_icon.show()
        show_toast(`Password set for ${data.file_name}`, 'success')
    } else {
        password_status_icon.hide()
        show_toast(`Password unset for ${data.file_name}`, 'success')
    }
    $('#setFilePasswordModal').hide()
}

function handle_private_toggle(data) {
    // TODO: Re-write this function and selectors
    // TODO: Use Logical Names for Selectors
    let someDropdown = $(`#file-${data.pk}-dropdown`)
    let dropdown_button_text = someDropdown.find('.privateText')
    let dropdown_button_icon = someDropdown.find('.privateDropdownIcon')
    // TODO: Use Actual Selectors
    let private_status_icon = $(`#file-${data.pk}`).find('#privateStatus')
    if (data.private) {
        show_toast(`File ${data.file_name} set to private.`, 'success')
        private_status_icon.show()
        dropdown_button_text.html('Make Public')
        dropdown_button_icon.removeClass('fa-lock').addClass('fa-lock-open')
    } else {
        show_toast(`File ${data.file_name} set to public.`, 'success')
        private_status_icon.hide()
        dropdown_button_text.html('Make Private')
        dropdown_button_icon.removeClass('fa-lock-open').addClass('fa-lock')
    }
}

function handle_set_expiration(data) {
    // TODO: Use Logical Names for Selectors
    let someSelector = $(`#file-${data.pk}`)
    let expire_status_icon = someSelector.find('#expireStatus')
    let expire_status_text = someSelector.find('#expireText')
    if (data.expr !== '') {
        expire_status_icon.show()
        expire_status_icon.attr('title', `File Expires in ${data.expr}`)
        expire_status_text.html(data.expr)
        show_toast(
            `Set expire for file ${data.file_name} to ${data.expr}`,
            'success'
        )
    } else {
        expire_status_icon.hide()
        expire_status_text.html('Never')
        show_toast(`Cleared expire for file ${data.file_name}`, 'success')
    }
}
