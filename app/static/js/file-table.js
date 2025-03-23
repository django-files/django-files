import { getContextMenu } from './file-context-menu.js'

import { socket } from './socket.js'

const filesTable = $('#files-table')

export const faLock = document.querySelector('div.d-none > .fa-lock')
export const faKey = document.querySelector('div.d-none > .fa-key')
export const faHourglass = document.querySelector('div.d-none > .fa-hourglass')
export const faCaret = document.querySelector(
    'div.d-none > .fa-square-caret-down'
)
export const fileLink = document.querySelector('div.d-none > .dj-file-link')
export const totalFilesCount = document.getElementById('total-files-count')

const fileExpireModal = $('#fileExpireModal')
const confirmDelete = $('#confirm-delete')
const fileDeleteModal = $('#fileDeleteModal')

let filesDataTable
let fileNameLength = getNameSize(window.innerWidth)

const dataTablesOptions = {
    paging: false,
    order: [1, 'desc'],
    responsive: {
        details: false,
    },
    processing: true,
    saveState: true,
    pageLength: -1,
    lengthMenu: [
        [1, 10, 25, 45, 100, 250, -1],
        [1, 10, 25, 45, 100, 250, 'All'],
    ],
    columns: [
        {
            data: null,
        },
        { data: 'id', name: 'id' },
        { data: 'name' },
        { data: 'size' },
        { data: 'mime' },
        { data: 'date' },
        { data: 'expr' },
        { data: 'password' },
        { data: 'private' },
        { data: 'view' },
    ],
    columnDefs: [
        {
            orderable: true,
            render: DataTable.render.select(),
            width: '10px',
            targets: 0,
            responsivePriority: 2,
        },
        {
            targets: 1,
            width: '15px',
            responsivePriority: 5,
            defaultContent: '',
        },
        {
            target: 2,

            responsivePriority: 1,
            render: getFileLink,
            defaultContent: '',
            type: 'html',
        },
        {
            targets: 3,
            render: formatBytes,
            defaultContent: '',
            responsivePriority: 4,
            width: '150px',
        },
        {
            targets: 4,
            defaultContent: '',
            responsivePriority: 9,
        },
        {
            name: 'date',
            targets: 5,
            render: DataTable.render.datetime('DD MMM YYYY, kk:mm'),
            defaultContent: '',
            responsivePriority: 8,
            width: '500px',
        },
        {
            targets: 6,
            width: '15px',
            defaultContent: '',
            className: 'expire-value text-center',
            responsivePriority: 7,
        },
        {
            targets: 7,
            width: '15px',
            render: getPwIcon,
            defaultContent: '',
            responsivePriority: 7,
        },
        {
            targets: 8,
            width: '15px',
            responsivePriority: 5,
            render: getPrivateIcon,
            defaultContent: '',
        },
        {
            targets: 9,
            width: '15px',
            defaultContent: '',
            responsivePriority: 4,
            className: 'text-center',
        },
        {
            targets: 10,
            orderable: false,
            width: '30px',
            responsivePriority: 3,
            render: getContextMenu,
            defaultContent: '',
        },
    ],
    select: {
        style: 'multi',
        selector: 'td:first-child',
    },
    language: {
        info: '',
    },
}

export function initFilesTable(search = true, ordering = true, info = true) {
    dataTablesOptions.searching = search
    dataTablesOptions.ordering = ordering
    dataTablesOptions.info = info
    // TODO: Disabling select boxes causes a bunch issues, we should address for cases we dont want select
    // if (!select) {
    //     delete dataTablesOptions.select
    //     dataTablesOptions.columnDefs.splice(0, 1)
    //     dataTablesOptions.columns.splice(0, 1)
    //     document.getElementById('files-table').rows[0].deleteCell(0)
    // }
    filesDataTable = filesTable.DataTable(dataTablesOptions)
    filesDataTable.on('draw.dt', debounce(dtDraw, 150))
    return filesDataTable
}

// ***************************
// Custom DataTables Renderers

function getFileLink(data, type, row, meta) {
    const fileLinkElem = fileLink.cloneNode(true)
    fileLinkElem.classList.add(`dj-file-link-${row.id}`)
    fileLinkElem
        .querySelector('.dj-file-link-clip')
        .setAttribute('data-clipboard-text', row.url)
    fileLinkElem.querySelector('.dj-file-link-ref').href = row.url
    fileLinkElem.querySelector('.dj-file-link-ref').ariaLabel = row.name

    let newName = row.name
    if (row.name.length > fileNameLength) {
        newName = row.name.substring(0, fileNameLength - 5) + '...'
    }
    fileLinkElem.querySelector('.dj-file-link-ref').textContent = newName
    return fileLinkElem
}

function getNameSize(width) {
    if (width < 380) {
        return 12
    } else if (screen.width > 380 && screen.width < 500) {
        return 20
    } else if (screen.width > 500 && screen.width < 1500) {
        return 40
    } else {
        return 60
    }
}

function getPwIcon(data, type, row, meta) {
    const pwIcon = faKey.cloneNode(true)
    pwIcon.classList.add('passwordStatus')
    if (!row.password) {
        pwIcon.style.display = 'none'
    }
    return pwIcon
}

function getPrivateIcon(data, type, row, meta) {
    const privateIcon = faLock.cloneNode(true)
    privateIcon.classList.add('privateStatus')
    if (!row.private) {
        privateIcon.style.display = 'none'
    }
    return privateIcon
}

// END Custom DataTables Renderers
// *******************************

/**
 * Convert Bytes to Human Readable Bytes
 * @function formatBytes
 * @param {Number} bytes
 * @return {String}
 */
export function formatBytes(bytes) {
    const decimals = 2
    if (bytes === 0) {
        return '0 Bytes'
    }
    const k = 1024
    const dm = decimals < 0 ? 0 : decimals
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i]
}

function dtDraw(event) {
    console.debug('dtDraw:', event)
    if (totalFilesCount) {
        totalFilesCount.textContent = filesDataTable.rows().count()
    }
}

export function addFileTableRow(file) {
    // adds a single file table entry with proper ID
    if (filesDataTable) {
        file['DT_RowId'] = `file-${file.id}`
        filesDataTable.row.add(file).draw()
    }
}

export function addFileTableRows(data) {
    // adds multiple file table entries
    for (const file of data.files) {
        addFileTableRow(file)
    }
}

export function removeFileTableRow(pk) {
    filesDataTable.row(`#file-${pk}`).remove().draw()
}

export function renameFileRow(data) {
    let fileName = document
        .getElementsByClassName(`dj-file-link-${data.id}`)[0]
        .getElementsByClassName('dj-file-link-ref')[0]
    let link = new URL(fileName.href)
    link.pathname = data.uri
    fileName.href = link.href
    fileName.innerHTML = data.name
}

socket?.addEventListener('message', function (event) {
    let data = JSON.parse(event.data)
    if (data.event === 'file-delete') {
        removeFileTableRow(data.id)
    } else if (data.event === 'file-new') {
        addFileTableRow(data)
    } else if (data.event === 'set-file-name') {
        renameFileRow(data)
    }
})

////////////////
// Bulk Actions
////////////////
// Todo: find a better place for these

// bulk delete actions
$('.bulk-delete').on('click', bulkDelete)

export function bulkDelete(event) {
    let pks = []
    filesDataTable.rows('.selected').every(function () {
        pks.push(this.data().id)
    })
    console.debug(`bulkDeleteFile: pks: ${pks}`, event)
    confirmDelete?.data('pks', pks)
    let s = ''
    if (pks.length > 1) s = 's'
    $('#fileDeleteModal #fileDeleteModalLabel').text(
        `Delete ${pks.length} File${s}`
    )
    $('#fileDeleteModal #fileDeleteModalBody').text(
        `Are you sure you want to delete ${pks.length} file${s}?`
    )
    fileDeleteModal.modal('show')
}

// bulk expire actions
$('.bulk-expire').on('click', bulkExpire)

export function bulkExpire(event) {
    let pks = []
    filesDataTable.rows('.selected').every(function () {
        pks.push(this.data().id)
    })
    console.debug(`bulkExpireFile: pks: ${pks}`, event)
    fileExpireModal.find('input[name=pks]').val(pks)
    let s = ''
    if (pks.length > 1) s = 's'
    $('#expr').val('')
    $('#fileExpireModal #fileExpireModalLabel').text(
        `Set ${pks.length} File Expirations`
    )
    $('#fileExpireModal #fileExpireModalBodyText').html(
        `This will set the expiration for ${pks.length} file${s}.`
    )
    fileExpireModal.modal('show')
}

// Start private expire actions
$('.bulk-private').on('click', bulkPrivate)

export function bulkPrivate(event) {
    let pks = []
    filesDataTable.rows('.selected').every(function () {
        pks.push(this.data().id)
    })
    socket.send(
        JSON.stringify({ method: 'private_files', pks: pks, private: true })
    )
}

// Start public expire actions
$('.bulk-public').on('click', bulkPublic)

export function bulkPublic(event) {
    let pks = []
    filesDataTable.rows('.selected').every(function () {
        pks.push(this.data().id)
    })
    socket.send(
        JSON.stringify({ method: 'private_files', pks: pks, private: false })
    )
}
