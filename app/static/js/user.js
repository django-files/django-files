// JS for logged in Users

// Get and set the csrf_token
const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

// Monitor websockets for new data and update results
socket.addEventListener('message', (event) => {
    console.log('user.js socket.addEventListener message function')
    let data = JSON.parse(event.data)
    console.log(data)
    if (data.event === 'file-new') {
        $.get(`/ajax/files/tdata/${data.pk}`, function () {
            let message = `New File Upload: ${data.pk}`
            show_toast(message, 'success', '10000')
            if (filesTable.length) {
                // console.log(response)
                console.log(`Table Updated: ${data.pk}`)
                $(`#file-${data.pk} .ctx-set-expire-btn`).on(
                    'click',
                    setExpireClick
                )
                $(`#file-${data.pk} .ctx-toggle-private-btn`).on(
                    'click',
                    togglePrivateClick
                )
                $(`#file-${data.pk} .ctx-set-password-btn`).on(
                    'click',
                    setPasswordClick
                )
                $(`#file-${data.pk} .ctx-delete-btn`).on(
                    'click',
                    deleteFileClick
                )
            }
        })
    } else if (data.event === 'file-delete') {
        let message = `File Deleted: ${data.pk}`
        show_toast(message, 'success', '10000')
        if (filesTable.length) {
            let count = $('#files-table tr').length
            $(`#file-${data.pk}`).remove()
            if (count <= 2) {
                console.log('removing #files-table@ #files-table')
                filesTable.remove()
            }
        }
    } else if (data.event === 'message') {
        console.log(`data.message: ${data.message}`)
        let bsclass =
            typeof data.bsclass === 'undefined' ? 'info' : data.bsclass
        console.log(`bsclass: ${bsclass}`)
        let delay = typeof data.delay === 'undefined' ? '10000' : data.delay
        console.log(`delay: ${delay}`)
        show_toast(data.message, data.bsclass, delay)
    }
})

// Init the logout form click function
$('.log-out').on('click', function (event) {
    event.preventDefault()
    $('#log-out').trigger('submit')
})

// Init the flush-cache click function
$('#flush-cache').on('click', function () {
    console.log('#flush-cache click function')
    $.ajax({
        url: '/flush-cache/',
        type: 'POST',
        headers: { 'X-CSRFToken': csrftoken },
        success: function (response) {
            console.log('response: ' + response)
            alert('Cache Flush Successfully Sent...')
            location.reload()
        },
        error: function (jqXHR) {
            console.log('jqXHR.status: ' + jqXHR.status)
            console.log('jqXHR.statusText: ' + jqXHR.statusText)
            let message = jqXHR.status + ': ' + jqXHR.statusText
            show_toast(message, 'danger', '10000')
        },
    })
    return false
})

// Set Expire Handler
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

// Toggle Private Handler
function togglePrivateClick() {
    const pk = $(this).parent().parent().parent().data('pk')
    console.log(`togglePrivateClick: ${pk}`)
    socket.send(JSON.stringify({ method: 'toggle-private-file', pk: pk }))
}

// Set Password Handler
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

// Delete Click Handler
function deleteFileClick() {
    const pk = $(this).parent().parent().parent().data('pk')
    console.log(`deleteFileClick: ${pk}`)
    $('#confirmDeleteFileBtn').data('pk', pk)
    $('#deleteFileModal').modal('show')
}
