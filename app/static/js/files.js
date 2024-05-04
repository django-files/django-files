// JS for Files

console.debug('LOADING: files.js')

const filesTable = $('#files-table')

const fileUploadModal = $('#fileUploadModal')

// document.addEventListener('dragenter', (event) => {
//     event.preventDefault()
//     fileUploadModal.modal('show')
// })

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

socket?.addEventListener('message', function (event) {
    // console.log('socket.message: files.js:', event)
    if (!filesTable.length) {
        return console.log('filesTable not found in DOM')
    }
    let data = JSON.parse(event.data)
    if (data.event === 'file-new') {
        $.get(`/ajax/files/tdata/${data.pk}`, function (response) {
            if (filesDataTable) {
                filesDataTable.row.add($(response)).draw()
            } else {
                filesTable.find('tbody').prepend(response)
            }
            const row = $(`#file-${data.pk}`)
            row.find('.ctx-expire').on('click', cxtSetExpire)
            row.find('.ctx-private').on('click', ctxSetPrivate)
            row.find('.ctx-password').on('click', ctxSetPassword)
            row.find('.ctx-delete').on('click', ctxDeleteFile)
        })
    } else if (data.event === 'file-delete') {
        console.log(`File Deleted: ${data.pk}`)
        $(`#file-${data.pk}`).remove()
    }
})

$('#user').on('change', function (event) {
    let user = $(this).val()
    console.log(`user: ${user}`)
    if (user) {
        let url = new URL(location.href)
        url.searchParams.set('user', user)
        location.href = url.toString()
    }
})

console.info('DROPZONE TESTING - KEEP CLEAR')

const dropTarget = document.getElementById('main-container')

// document.addEventListener('dragenter', (event) => {
//     console.debug('dragenter', event)
//     event.preventDefault()
//     dropOverlay.classList.remove('d-none')
// })
// document.addEventListener('dragend', (event) => {
//     console.debug('dragend', event)
//     event.preventDefault()
//     dropOverlay.classList.add('d-none')
// })
// document.addEventListener('dragleave', (event) => {
//     console.debug('dragleave', event)
//     event.preventDefault()
//     dropOverlay.classList.add('d-none')
// })
//
// let counter = 0
// document.addEventListener('dragenter', (event) => {
//     event.preventDefault()
//     if (counter++ === 0) {
//         console.log('entered the page')
//         dropOverlay.classList.remove('d-none')
//     }
// })
// document.addEventListener('dragleave', (event) => {
//     event.preventDefault()
//     if (--counter === 0) {
//         console.log('left the page')
//         dropOverlay.classList.add('d-none')
//     }
// })

dropTarget.addEventListener('dragenter', (event) => {
    console.debug('dragenter', event)
    event.preventDefault()
})
dropTarget.addEventListener('dragover', (event) => {
    console.debug('dragover', event)
    event.preventDefault()
})
dropTarget.addEventListener('drop', (event) => {
    console.debug('drop', event)
    const dataTransfer = event.dataTransfer
    event.preventDefault()
    console.debug('dataTransfer', dataTransfer)
    fileUploadModal.modal('show')
    uppy.addFile(dataTransfer.files[0])
})
