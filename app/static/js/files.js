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
        $.get(`/ajax/files/tdata/${data.pk}`, (response) => {
            console.log(`Table Updated: ${data.pk}`)
            // console.log('response:', response)
            if (filesTable.length) {
                if (filesDataTable) {
                    filesDataTable.row.add($(response)).draw()
                } else {
                    filesTable.find('tbody').prepend(response)
                }
            }
            const row = $(`#file-${data.pk}`)
            // console.log('row:', row)
            row.find('.ctx-expire').on('click', cxtSetExpire)
            row.find('.ctx-private').on('click', ctxSetPrivate)
            row.find('.ctx-password').on('click', ctxSetPassword)
            row.find('.ctx-delete').on('click', ctxDeleteFile)
        })
    } else if (data.event === 'file-delete') {
        $(`#file-${data.pk}`).remove()
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
