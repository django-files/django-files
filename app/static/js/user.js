// Get and set the csrf_token
const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

// Define Datatables inside filesTable.length because render uses DataTable.render
let filesDataTable
const filesTable = $('#files-table')
if (filesTable.length) {
    filesDataTable = filesTable.DataTable({
        order: [0, 'desc'],
        processing: true,
        saveState: true,
        pageLength: -1,
        lengthMenu: [
            [10, 25, 50, 100, 250, -1],
            [10, 25, 50, 100, 250, 'All'],
        ],
        columnDefs: [
            { targets: 2, type: 'file-size' },
            {
                targets: 4,
                render: DataTable.render.datetime('DD MMM YYYY, kk:mm'),
            },
            { targets: [6, 7, 9], orderable: false },
        ],
    })
}

// Monitor websockets for new data and update results
socket.addEventListener('message', (event) => {
    console.log('user.js socket.addEventListener message function')
    let data = JSON.parse(event.data)
    console.log(data)
    if (data.event === 'file-new') {
        $.get(`/ajax/files/tdata/${data.pk}`, function (response) {
            let message = `New File Upload: ${data.pk}`
            show_toast(message, 'success', '10000')
            if (filesTable.length) {
                // $('#files-table tbody').prepend(response)
                // console.log(response)
                filesDataTable.row.add($(response)).draw()
                // filesDataTable.sort()
                console.log(`Table Updated: ${data.pk}`)
                $(`#file-${data.pk} .ctx-set-expire-btn`).click(setExpireClick)
                $(`#file-${data.pk} .ctx-toggle-private-btn`).click(
                    togglePrivateClick
                )
                $(`#file-${data.pk} .ctx-set-password-btn`).click(
                    setPasswordClick
                )
                $(`#file-${data.pk} .ctx-delete-btn`).click(deleteFileClick)
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
$('.log-out').on('click', function () {
    $('#log-out').submit()
    return false
})

// Init the flush-cache click function
$('#flush-cache').click(function () {
    console.log('flush-cache clicked...')
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
    console.log(`.ctx-set-expire-btn: pk: ${pk}`)
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
    console.log(`.ctx-toggle-private-btn: pk: ${pk}`)
    socket.send(JSON.stringify({ method: 'toggle-private-file', pk: pk }))
}

// Set Password Handler
function setPasswordClick() {
    const pk = $(this).parent().parent().parent().data('pk')
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
}

// Delete Click Handler
function deleteFileClick() {
    const pk = $(this).parent().parent().parent().data('pk')
    console.log(`.ctx-delete-btn: pk: ${pk}`)
    $('#confirmDeleteFileBtn').data('pk', pk)
    $('#deleteFileModal').modal('show')
}
