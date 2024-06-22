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

let filesDataTable

const dataTablesOptions = {
    paging: false,
    order: [0, 'desc'],
    responsive: true,
    processing: true,
    saveState: true,
    pageLength: -1,
    lengthMenu: [
        [10, 25, 50, 100, 250, -1],
        [10, 25, 50, 100, 250, 'All'],
    ],
    columns: [
        { data: 'id' },
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
            targets: 0,
            width: '30px',
            responsivePriority: 5,
            defaultContent: '',
        },
        {
            target: 1,
            width: '40%',
            responsivePriority: 1,
            render: getFileLink,
            defaultContent: '',
            type: 'html',
        },
        {
            targets: 2,
            render: formatBytes,
            defaultContent: '',
            responsivePriority: 3,
        },
        { targets: 3, defaultContent: '', responsivePriority: 9 },
        {
            name: 'date',
            targets: 4,
            render: DataTable.render.datetime('DD MMM YYYY, kk:mm'),
            defaultContent: '',
            responsivePriority: 8,
            width: '170px',
        },
        {
            targets: 5,
            width: '30px',
            defaultContent: '',
            className: 'expire-value text-center',
            responsivePriority: 7,
        },
        {
            targets: 6,
            width: '30px',
            render: getPwIcon,
            defaultContent: '',
            responsivePriority: 7,
        },
        {
            targets: 7,
            width: '30px',
            responsivePriority: 5,
            render: getPrivateIcon,
            defaultContent: '',
        },
        {
            targets: 8,
            width: '30px',
            defaultContent: '',
            responsivePriority: 4,
            className: 'text-center',
        },
        {
            targets: 9,
            orderable: false,
            width: '30px',
            responsivePriority: 2,
            render: getContextMenu,
            defaultContent: '',
        },
    ],
}

export function initFilesTable(search = true, ordering = true, info = true) {
    dataTablesOptions.searching = search
    dataTablesOptions.ordering = ordering
    dataTablesOptions.info = info
    filesDataTable = filesTable.DataTable(dataTablesOptions)
    filesDataTable.on('draw.dt', debounce(dtDraw, 150))
    console.log(filesDataTable.columns)
    return filesDataTable
}

// ***************************
// Custom DataTables Renderers

function getFileLink(data, type, row, meta) {
    let max_name_length
    if (screen.width < 500) {
        max_name_length = 20
    } else if (screen.width > 500 && screen.width < 1500) {
        max_name_length = 40
    } else {
        max_name_length = 60
    }
    const fileLinkElem = fileLink.cloneNode(true)
    fileLinkElem.classList.add(`dj-file-link-${row.id}`)
    fileLinkElem
        .querySelector('.dj-file-link-clip')
        .setAttribute('data-clipboard-text', row.url)
    fileLinkElem.querySelector('.dj-file-link-ref').href = row.url
    fileLinkElem.querySelector('.dj-file-link-ref').ariaLabel = row.name

    let newName = row.name
    if (row.name.length > max_name_length) {
        newName = row.name.substring(0, max_name_length) + '...'
    }
    fileLinkElem.querySelector('.dj-file-link-ref').textContent = newName
    return fileLinkElem
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
