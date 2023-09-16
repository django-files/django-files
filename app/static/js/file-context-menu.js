$(document).ready(function () {
    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

    // Define Hook Modal and Delete handlers
    const deleteHookModal = new bootstrap.Modal('#deleteFileModal', {})

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
    let pwpk
    $('.set-password-file-btn').click(function () {
        pwpk = $(this).data('pk')
        console.log(pwpk)
        setPasswordHookModal.show()
    })

    // Handle set password click confirmations
    $('#confirm-set-password-hook-btn').click(function (event) {
        event.preventDefault()
        if ($('#confirm-set-password-hook-btn').hasClass('disabled')) {
            return
        }
        let formData = new $('#set-password-form').serialize()
        console.log(formData)
        console.log(pwpk)
        $.ajax({
            type: 'POST',
            url: `/ajax/set_password/file/${pwpk}/`,
            headers: { 'X-CSRFToken': csrftoken },
            data: formData,
            beforeSend: function () {
                console.log('beforeSend')
                $('#confirm-set-password-hook-btn').addClass('disabled')
            },
            success: function (response) {
                console.log('response: ' + response)
                setPasswordHookModal.hide()
                let message = 'Password set!'
                show_toast(message, 'success')
            },
            error: function (xhr, status, error) {
                console.log('xhr status: ' + xhr.status)
                console.log('status: ' + status)
                console.log('error: ' + error)
                setPasswordHookModal.hide()
                let message = xhr.status + ': ' + error
                show_toast(message, 'danger', '15000')
            },
            complete: function () {
                console.log('complete')
                $('#confirm-set-password-hook-btn').removeClass('disabled')
            },
        })
    })

    // Handle toggling file private status
    $('.toggle-private-btn').click(function (event) {
        event.preventDefault()
        console.log("ping")
        let pvpk = $(this).data('pk')
        if ($('#toggle-private-btn').hasClass('disabled')) {
            return
        }
        console.log(pvpk)
        let private_status = $('#privateStatus')
        let toggle_status = $('#toggleStatus')
        let toggle_text = $('#toggleText')
        $.ajax({
            type: 'POST',
            url: `/ajax/toggle_private/file/${pvpk}/`,
            headers: { 'X-CSRFToken': csrftoken },
            success: function (response) {
                console.log('response: ' + response)
                let isTrueSet = response === 'True'
                let message
                if (isTrueSet) {
                    message = 'File made private!'
                    private_status.title = 'Private File'
                    private_status
                        .removeClass('fa-lock-open')
                        .addClass('fa-lock')
                    toggle_status
                        .removeClass('fa-lock')
                        .addClass('fa-lock-open')
                    toggle_text.text(
                        toggle_text.text().replace('Private', 'Public')
                    )
                } else {
                    message = 'File made public!'
                    private_status.title = 'Public File'
                    private_status
                        .removeClass('fa-lock')
                        .addClass('fa-lock-open')
                    toggle_status
                        .removeClass('fa-lock-open')
                        .addClass('fa-lock')
                    toggle_text.text(
                        toggle_text.text().replace('Public', 'Private')
                    )
                }
                show_toast(message, 'success')
            },
            error: function (xhr, status, error) {
                console.log('xhr status: ' + xhr.status)
                console.log('status: ' + status)
                console.log('error: ' + error)
                let message = xhr.status + ': ' + error
                show_toast(message, 'danger', '15000')
            },
        })
    })

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


    // Set Expire Hook Modal and Set Expire handlers
    let exprpk
    $('.set-expr-btn').click(function () {
        exprpk = $(this).data('pk')
        console.log(exprpk)
        $('#confirmFileExprBtn').data('pk', exprpk)
        $('#setFileExprModal').modal('show')
    })

    // Handle set expire click confirmations
    $('#confirmExprFileBtn').click(function (event) {
        event.preventDefault()
        if ($('#confirmFileExprBtn').hasClass('disabled')) {
            return
        }
        let formData = new $('#set-expr-form').serialize()
        console.log(formData)
        console.log(exprpk)
        $.ajax({
            type: 'POST',
            url: `/ajax/set_expr/file/${exprpk}/`,
            headers: { 'X-CSRFToken': csrftoken },
            data: formData,
            beforeSend: function () {
                console.log('beforeSend')
                $('#confirmFileExprBtn').addClass('disabled')
            },
            success: function (response) {
                console.log('response: ' + response)
                $('#setFileExprModal').modal('hide')
                let message = 'File Expiration set!'
                show_toast(message, 'success')
            },
            error: function (xhr, status, error) {
                console.log('xhr status: ' + xhr.status)
                console.log('status: ' + status)
                console.log('error: ' + error)
                $('#setFileExprModal').modal('hide')
                let message = xhr.status + ': ' + error
                show_toast(message, 'danger', '15000')
            },
            complete: function () {
                console.log('complete')
                $('#confirmFileExprBtn').removeClass('disabled')
                let expr = formData.replace('expr=', '')
                let expire_status = $('#expireStatus')
                expire_status.attr('title', `File Expires in ${expr}`);
                if (expr == '') {
                    console.log("hiding")
                    expire_status.hide();
                } else {
                    console.log("showing")
                    expire_status.show();
                }

            },
        })
    })
})
