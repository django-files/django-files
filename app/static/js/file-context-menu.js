$(document).ready(function () {
    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

    socket.addEventListener("message", function (event) {
        let data = JSON.parse(event.data)
        console.log(data)
        if (data.event === 'toggle-private-file') {
            handle_private_toggle(data)
        } else if (data.event === 'set-expr-file') {
            handle_set_expiration(data)
        } else if (data.event === 'set-password-file') {
            handle_password_set(data)
        }
    });

    let pk

    $('.delete-file-btn').click(function () {
        let pk = $(this).data('pk')
        console.log(`Delete Button: pk: ${pk}`)
        $('#confirmDeleteFileBtn').data('pk', pk)
        $('#deleteFileModal').modal('show')
    })

    // Handle delete click confirmations
    $('#confirmDeleteFileBtn').click(function () {
        let pk = $(this).data('pk')
        console.log(`Confirm Delete: pk: ${pk}`)
        socket.send(JSON.stringify({ method: 'delete-file', pk: pk }))
        $('#deleteFileModal').modal('hide')
    })

    // Set Password Hook Modal and Set Password handlers
    const setPasswordHookModal = new bootstrap.Modal(
        '#setFilePasswordModal',
        {}
    )

    $('.set-password-file-btn').click(function () {
        pk = $(this).data('pk')
        console.log(pk)
        $('#confirm-set-password-hook-btn').data('pk', pk)
        let passwordText = $(`#file-${pk}-dropdown`).find('.file-password-value').val()
        $('#setFilePasswordModal').find('#password').val(passwordText)
        setPasswordHookModal.show()
    })

    // Handle set password click confirmations
    $('#confirm-set-password-hook-btn').click(function (event) {
        event.preventDefault()
        if ($('#confirm-set-password-hook-btn').hasClass('disabled')) {
            return
        }
        let formData = new $('#set-password-form').serializeArray()
        socket.send(JSON.stringify({ method: 'set-password-file', pk: pk, password: formData[0].value }))
        $(`#file-${pk}`).find('.file-password-value').val(formData[0].value)
    })

    function handle_password_set(data) {
        let message
        let password_status_icon = $(`#file-${data.pk}`).find("#passwordStatus")
        if (data.password) {
            password_status_icon.show()
            message = `Password set for ${data.file_name}`
        } else {
            password_status_icon.hide()
            message = `Password unset for ${data.file_name}`
        }
        show_toast(message, 'success')
        setPasswordHookModal.hide()
    }

    $('.toggle-private-btn').click(function (event) {
        event.preventDefault()
        let pk = $(this).data('pk')
        console.log(pk)
        socket.send(JSON.stringify({ method: 'toggle-private-file', pk: pk }))
    })

    function handle_private_toggle(data) {
        let message
        let dropdown_button_text = $(`#file-${data.pk}-dropdown`).find("#privateText")
        let dropdown_button_icon = $(`#file-${data.pk}-dropdown`).find("#privateDropdownIcon")
        let private_status_icon = $(`#file-${data.pk}`).find("#privateStatus")
        if (data.private) {
            message = `File ${data.file_name} set to private.`
            private_status_icon.show()
            dropdown_button_text.html('Make Public')
            dropdown_button_icon.removeClass('fa-lock')
            dropdown_button_icon.addClass('fa-lock-open')
        } else {
            message = `File ${data.file_name} set to public.`
            private_status_icon.hide()
            dropdown_button_text.html('Make Private')
            dropdown_button_icon.removeClass('fa-lock-open')
            dropdown_button_icon.addClass('fa-lock')
        }
        show_toast(message, 'success')
    }

    $('#unMaskPassword').click(function () {
        let password_field = $('#password').get(0)
        if (password_field.type === 'password') {
            password_field.type = 'text'
        } else {
            password_field.type = 'password'
        }
    })

    $('#copyPassword').click(function () {
        let password_field = $('#password').get(0)
        navigator.clipboard.writeText(password_field.value)
        show_toast('Password copied!', 'info', '15000')
    })

    $('#generatePassword').click(function () {
        // TODO: Cleanup this Listener
        let chars = '0123456789abcdefghijklmnopqrstuvwxyz!+()ABCDEFGHIJKLMNOPQRSTUVWXYZ';
        let pwordLength = 15;
        let password = '';

        const array = new Uint32Array(chars.length);
        window.crypto.getRandomValues(array);

        for (let i = 0; i < pwordLength; i++) {
        password += chars[array[i] % chars.length];
        }
        $('#password').get(0).value = password
        navigator.clipboard.writeText(password)
        show_toast('Password generated and copied!', 'info', '15000')
    })

    $('#setFilePasswordModal').on('shown.bs.modal', function () {
        $('#password').focus()
    })



    $('.set-expr-btn').click(function () {
        pk = $(this).data('pk')
        $('#confirmFileExprBtn').data('pk', pk)
        let expireText = $(`#file-${pk}`).find('#expireText')
        if (expireText.length > 0 ) {
            let value = expireText.html()
            if (value == 'Never') {
                value = ''
            }
            $('#setFileExprModal').find('#expr').val(value)
        }
        $('#setFileExprModal').modal('show')
    })


    $('#confirmExprFileBtn').click(function (event) {
        event.preventDefault()
        if ($('#confirmFileExprBtn').hasClass('disabled')) {
            return
        }
        let formData = new $('#set-expr-form').serializeArray()
        socket.send(JSON.stringify({ method: 'set-expr-file', pk: pk, expr: formData[0].value}))
        $('#setFileExprModal').modal('hide')
    })

    function handle_set_expiration(data) {
        let message
        let expire_status_icon = $(`#file-${data.pk}`).find("#expireStatus")
        let expire_status_text = $(`#file-${data.pk}`).find("#expireText")
        if (data.expr != "") {
            expire_status_icon.show()
            expire_status_icon.attr('title', `File Expires in ${data.expr}`)
            expire_status_text.html(data.expr)
            message = `Set expire for file ${data.file_name} to ${data.expr}`
        } else {
            expire_status_icon.hide()
            message = `Cleared expire for file ${data.file_name}`
            expire_status_text.html('Never')
        }
        show_toast(message, 'success')
    }

})
