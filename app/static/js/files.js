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

socket?.addEventListener('message', (event) => {
    console.log('socket: files.js:', event)
    let data = JSON.parse(event.data)
    if (data.event === 'file-new') {
        $.get(`/ajax/files/tdata/${data.pk}`, function (response) {
            console.log(`Table Updated: ${data.pk}`)
            // console.log(response)
            if (filesTable.length) {
                if (filesTable.length && filesDataTable) {
                    filesDataTable.row.add($(response)).draw()
                } else {
                    $('#files-table tbody').prepend(response)
                }
                $(`#file-${data.pk} .ctx-expire`).on('click', setExpireClick)
                $(`#file-${data.pk} .ctx-private`).on(
                    'click',
                    togglePrivateClick
                )
                $(`#file-${data.pk} .ctx-password`).on(
                    'click',
                    setPasswordClick
                )
                $(`#file-${data.pk} .ctx-delete`).on('click', deleteFileClick)
            }
        })
    } else if (data.event === 'file-delete') {
        if (filesTable.length) {
            let count = $('#files-table tr').length
            $(`#file-${data.pk}`).remove()
            if (count <= 2) {
                console.log('removing #files-table@ #files-table')
                filesTable.remove()
            }
        }
    }
})

$('#user').on('change', () => {
    let user = $(this).val()
    console.log('user: ' + user)
    if (user) {
        let url = new URL(location.href)
        url.searchParams.set('user', user)
        location.href = url.toString()
    }
})
