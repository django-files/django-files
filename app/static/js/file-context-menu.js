$(document).ready(function () {
    socket.addEventListener('message', function (event) {
        const data = JSON.parse(event.data)
        if (data.event === 'set-expr-file') {
            handle_set_expiration(data)
        }
        // } else if (data.event === 'toggle-private-file') {
        //     handle_private_toggle(data)
        // } else if (data.event === 'set-password-file') {
        //     handle_password_set(data)
        // }
    })

    // EXPIRE
    //
    $('.ctx-set-expire-btn').click(function () {
        const pk = $(this).data('pk')
        console.log(`.ctx-set-expire-btn: pk: ${pk}`)
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
        console.log(`#set-expr-form.submit: pk: ${pk}`)
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

    // // PASSWORD
    // //
    // // Set Password Context Menu Button
    // $('.ctx-set-password-btn').click(function () {
    //     const pk = $(this).data('pk')
    //     console.log(`.ctx-set-password-btn: pk: ${pk}`)
    //     $('#setFilePasswordModal input[name=pk]').val(pk)
    //     const setFilePasswordModal = new bootstrap.Modal(
    //         '#setFilePasswordModal'
    //     )
    //     // const setFilePasswordModal = $('#setFilePasswordModal')
    //     // TODO: Use Actual Selectors
    //     const currentPassInput = $(
    //         `#ctx-menu-${pk} input[name=current-password]`
    //     )
    //     console.log(`currentInput: ${currentPassInput}`)
    //     const passwordText = currentPassInput.val()
    //     console.log(`passwordText: ${passwordText}`)
    //     $('#password').val(passwordText)
    //     setFilePasswordModal.show()
    // })
    // // Set Password Form Submission
    // $('#set-password-form').submit(function (event) {
    //     event.preventDefault()
    //     // TODO: pk is not defined here
    //     const pk = $(this).data('pk')
    //     console.log(`#set-password-form.submit: pk: ${pk}`)
    //     let formData = new $('#set-password-form').serializeArray()
    //     socket.send(
    //         JSON.stringify({
    //             method: 'set-password-file',
    //             pk: pk,
    //             password: formData[0].value,
    //         })
    //     )
    //     // TODO: Use Actual Selectors
    //     $(`#file-${pk}`).find('.file-password-value').val(formData[0].value)
    // })
    // $('.ctx-toggle-private-btn').click(function (event) {
    //     event.preventDefault()
    //     let pk = $(this).data('pk')
    //     console.log(`.ctx-toggle-private-btn: pk: ${pk}`)
    //     socket.send(JSON.stringify({ method: 'toggle-private-file', pk: pk }))
    // })
    // $('#unMaskPassword').click(function () {
    //     const password = $('#password')
    //     console.log(`#unMaskPassword: password: ${password}`)
    //     const type = password.type === 'password' ? 'text' : 'password'
    //     password.prop('type', type)
    // })
    // // TODO: Why do we need a custom function for this vs clipboardjs
    // $('#copyPassword').click(async function () {
    //     await navigator.clipboard.writeText($('#password').val())
    //     show_toast('Password copied!', 'info', '15000')
    // })
    // $('#generatePassword').click(async function () {
    //     // TODO: Cleanup this Listener
    //     console.log('#generatePassword.click')
    //     const chars =
    //         '0123456789abcdefghijklmnopqrstuvwxyz!+()ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    //     const pwordLength = 15
    //     let password = ''
    //
    //     const array = new Uint32Array(chars.length)
    //     window.crypto.getRandomValues(array)
    //
    //     for (let i = 0; i < pwordLength; i++) {
    //         password += chars[array[i] % chars.length]
    //     }
    //     $('#password').val(password)
    //     await navigator.clipboard.writeText(password)
    //     show_toast('Password generated and copied!', 'info', '15000')
    // })
    // $('#setFilePasswordModal').on('shown.bs.modal', function () {
    //     $('#password').focus()
    // })

    // // DELETE
    // //
    // // Delete File Context Menu Button
    // $('.ctx-delete-btn').click(function () {
    //     const pk = $(this).data('pk')
    //     console.log(`.ctx-delete-btn: pk: ${pk}`)
    //     $('#confirmDeleteFileBtn').data('pk', pk)
    //     $('#deleteFileModal').modal('show')
    // })
    // // Delete File Confirm Button
    // $('#confirmDeleteFileBtn').click(function () {
    //     const pk = $(this).data('pk')
    //     console.log(`#confirmDeleteFileBtn: pk: ${pk}`)
    //     socket.send(JSON.stringify({ method: 'delete-file', pk: pk }))
    //     $('#deleteFileModal').modal('hide')
    // })
})

function handle_set_expiration(data) {
    // TODO: Use Logical Names for Selectors
    console.log(`handle_set_expiration: data: ${data}`)
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

// function handle_private_toggle(data) {
//     // TODO: Re-write this function and selectors
//     // TODO: Use Logical Names for Selectors
//     console.log(`handle_private_toggle: data: ${data}`)
//     let someDropdown = $(`#file-${data.pk}-dropdown`)
//     let dropdown_button_text = someDropdown.find('.privateText')
//     let dropdown_button_icon = someDropdown.find('.privateDropdownIcon')
//     // TODO: Use Actual Selectors
//     let private_status_icon = $(`#file-${data.pk}`).find('#privateStatus')
//     if (data.private) {
//         show_toast(`File ${data.file_name} set to private.`, 'success')
//         private_status_icon.show()
//         dropdown_button_text.html('Make Public')
//         dropdown_button_icon.removeClass('fa-lock').addClass('fa-lock-open')
//     } else {
//         show_toast(`File ${data.file_name} set to public.`, 'success')
//         private_status_icon.hide()
//         dropdown_button_text.html('Make Private')
//         dropdown_button_icon.removeClass('fa-lock-open').addClass('fa-lock')
//     }
// }
//
// function handle_password_set(data) {
//     // TODO: Use Actual Selectors
//     console.log(`handle_password_set: data: ${data}`)
//     $(`#file-${data.pk} .passwordStatus`).toggle()
//     if (data.password) {
//         show_toast(`Password set for ${data.file_name}`, 'success')
//     } else {
//         show_toast(`Password unset for ${data.file_name}`, 'success')
//     }
//     $('#setFilePasswordModal').hide()
// }
