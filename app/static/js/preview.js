$(document).ready(function () {
    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

    // Define Hook Modal and Delete handlers
    const deleteHookModal = new bootstrap.Modal('#delete-file-modal', {})
    let hookID
    $('.delete-file-btn').click(function () {
        hookID = $(this).data('hook-id')
        console.log(hookID)
        deleteHookModal.show()
    })

    // Handle delete click confirmations
    $('#confirm-delete-hook-btn').click(function () {
        if ($('#confirm-delete-hook-btn').hasClass('disabled')) {
            return
        }
        console.log(hookID)
        $.ajax({
            type: 'POST',
            url: `/ajax/delete/file/${hookID}/`,
            headers: { 'X-CSRFToken': csrftoken },
            beforeSend: function () {
                console.log('beforeSend')
                $('#confirm-delete-hook-btn').addClass('disabled')
            },
            success: function (response) {
                console.log('response: ' + response)
                deleteHookModal.hide()
                console.log('removing #file-' + hookID)
                let count = $('#files-table tr').length
                $('#file-' + hookID).remove()
                if (count <= 2) {
                    console.log('removing #files-table@ #files-table')
                    $('#files-table').remove()
                }
                let message = 'File ' + hookID + ' Successfully Removed.'
                show_toast(message, 'success')
            },
            error: function (xhr, status, error) {
                console.log('xhr status: ' + xhr.status)
                console.log('status: ' + status)
                console.log('error: ' + error)
                deleteHookModal.hide()
                let message = xhr.status + ': ' + error
                show_toast(message, 'danger', '15000')
            },
            complete: function () {
                console.log('complete')
                $('#confirm-delete-hook-btn').removeClass('disabled')
                window.location.replace('/files/')
            },
        })
    })


        // Set Password Hook Modal and Set Password handlers
        const setPasswordHookModal = new bootstrap.Modal('#set-password-file-modal', {})
        let pwhookID
        $('.set-password-file-btn').click(function () {
            pwhookID = $(this).data('hook-id')
            console.log(pwhookID)
            setPasswordHookModal.show()
        })
    
        // Handle set password click confirmations
        $('#confirm-set-password-hook-btn').click(function () {
            event.preventDefault()
            if ($('#confirm-set-password-hook-btn').hasClass('disabled')) {
                return
            }
            var formData = new $("#set-password-form").serialize()
            console.log(formData)
            console.log(pwhookID)
            $.ajax({
                type: 'POST',
                url: `/ajax/set_password/file/${pwhookID}/`,
                headers: { 'X-CSRFToken': csrftoken },
                data: formData,
                beforeSend: function () {
                    console.log('beforeSend')
                    $('#confirm-set-password-hook-btn').addClass('disabled')
                },
                success: function (response) {
                    console.log('response: ' + response)
                    setPasswordHookModal.hide()
                    message = 'Error Setting Password!'
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

        $('#unMaskPassword').click(function(){
            var password_field = $('#password').get(0)
            if (password_field.type === "password") {
                password_field.type = "text";
              } else {
                password_field.type = "password";
              }
        });

        $('#copyPassword').click(function(){
            var password_field = $('#password').get(0);
            navigator.clipboard.writeText(password_field.value);
            show_toast("Password copied!", 'info', '15000');
        });

        $('#generatePassword').click(function(){
            var chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
            var passwordLength = 12;
            var password = "";
            for (var i = 0; i <= passwordLength; i++) {
                var randomNumber = Math.floor(Math.random() * chars.length);
                password += chars.substring(randomNumber, randomNumber +1);
               }
            $('#password').get(0).value = password;
            navigator.clipboard.writeText(password);
            show_toast("Password generated and copied!", 'info', '15000');
        });


});

