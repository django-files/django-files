// JS for Files

const filesTable = $('#files-table')

let filesDataTable
if (typeof DataTable !== 'undefined' && filesTable.length) {
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
socket?.addEventListener('message', (event) => {
    console.log('files.js socket.addEventListener message:', event)
    let data = JSON.parse(event.data)
    if (data.event === 'file-new') {
        $.get(`/ajax/files/tdata/${data.pk}`, function (response) {
            console.log(`Table Updated: ${data.pk}`)
            // console.log(response)
            if (filesTable.length) {
                if (filesTable.length && filesDataTable) {
                    filesDataTable.row.add($(response)).draw()
                }
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
    }
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

$('#user').on('change', () => {
    let user = $(this).val()
    console.log('user: ' + user)
    if (user) {
        let url = new URL(location.href)
        url.searchParams.set('user', user)
        location.href = url.toString()
    }
})
