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
            if (filesTable.length && filesDataTable) {
                filesDataTable.row.add($(response)).draw()
                console.log(`Table Updated: ${data.pk}`)
            }
        })
    }
})

$('#user').on('change', function () {
    let user = $(this).val()
    console.log('user: ' + user)
    if (user) {
        let url = new URL(location.href)
        url.searchParams.set('user', user)
        location.href = url.toString()
    }
})
