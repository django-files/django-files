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

window.addEventListener(
    'resize',
    debounce(function () {
        fileNameLength = getNameSize(window.innerWidth)
        if (filesDataTable) {
            filesDataTable.rows().invalidate('data').draw(false)
        }
    }, 100),
    { passive: true }
)

const dataTablesOptions = {
    paging: false,
    order: [1, 'desc'],
    responsive: {
        details: false,
    },
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
            responsivePriority: 8,
            defaultContent: '',
        },
        {
            target: 2,
            responsivePriority: 1,
            render: getFileLink,
            defaultContent: '',
            type: 'html',
            className: 'dt-name-col',
        },
        {
            targets: 3,
            render: formatBytes,
            defaultContent: '',
            responsivePriority: 9,
            width: '150px',
        },
        {
            targets: 4,
            defaultContent: '',
            responsivePriority: 10,
            className: 'text-nowrap',
        },
        {
            name: 'date',
            targets: 5,
            render: DataTable.render.datetime('DD MMM YYYY, kk:mm'),
            defaultContent: '',
            responsivePriority: 10,
            width: '165px',
            className: 'text-nowrap',
        },
        {
            targets: 6,
            width: '15px',
            defaultContent: '',
            className: 'expire-value text-center',
            responsivePriority: 10,
        },
        {
            targets: 7,
            width: '15px',
            render: getPwIcon,
            defaultContent: '',
            responsivePriority: 4,
        },
        {
            targets: 8,
            width: '15px',
            responsivePriority: 4,
            render: getPrivateIcon,
            defaultContent: '',
        },
        {
            targets: 9,
            width: '15px',
            defaultContent: '',
            responsivePriority: 8,
            className: 'text-center',
        },
        {
            targets: 10,
            orderable: false,
            width: '30px',
            responsivePriority: 3,
            render: getContextMenu,
            defaultContent: '',
            className: 'dt-ctx-menu-col',
        },
    ],
    select: {
        style: 'multi',
        selector: 'td:first-child',
    },
    language: {
        info: '',
        emptyTable: '',
        loadingRecords: '',
        zeroRecords: '',
    },
    initComplete: function () {
        const container = $(this.api().table().container())
        const startCell = container.find('.dt-layout-start').first()
        const endCell = container.find('.dt-layout-end').first()

        const bulkWrapper = document.getElementById('dt-bulk-wrapper')
        if (bulkWrapper) {
            startCell.append(bulkWrapper)
            bulkWrapper.classList.remove('d-none')
        }

        // Prepend in reverse visual order — each prepend goes to position 0,
        // so the last prepended element ends up leftmost in the flex end cell.
        const userSelectWrapper = document.getElementById(
            'dt-user-select-wrapper'
        )
        if (userSelectWrapper) {
            endCell.prepend(userSelectWrapper)
            userSelectWrapper.classList.remove('d-none')
        }

        const fileCountWrapper = document.getElementById(
            'dt-file-count-wrapper'
        )
        if (fileCountWrapper) {
            startCell.append(fileCountWrapper)
            fileCountWrapper.classList.remove('d-none')
        }

        // Double-rAF ensures the browser commits layout before the opacity transition starts
        const section = document.getElementById('files-table-section')
        if (section) {
            requestAnimationFrame(() =>
                requestAnimationFrame(() =>
                    section.classList.add('dt-section-ready')
                )
            )
        }

        // Restore empty-state messages. No explicit draw needed — the caller's
        // data-load draw (or columns.adjust().draw()) will use these strings.
        initDtLang(this.api(), 'No files available', 'No matching files found')
    },
}

export function initFilesTable(search = true, ordering = true, info = true) {
    dataTablesOptions.searching = search
    dataTablesOptions.ordering = ordering
    dataTablesOptions.info = info
    filesDataTable = filesTable.DataTable(dataTablesOptions)
    filesDataTable.on('draw.dt', debounce(dtDraw, 150))
    return filesDataTable
}

function getFileLink(data, type, row, _meta) {
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
    return Math.round(0.04 * width + 8)
}

function getPwIcon(data, type, row, _meta) {
    const pwIcon = faKey.cloneNode(true)
    pwIcon.classList.add('passwordStatus')
    if (!row.password) {
        pwIcon.classList.add('d-none')
    }
    return pwIcon
}

function getPrivateIcon(data, type, row, _meta) {
    const privateIcon = faLock.cloneNode(true)
    privateIcon.classList.add('privateStatus')
    if (!row.private) {
        privateIcon.classList.add('d-none')
    }
    return privateIcon
}

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
    if (filesDataTable) {
        file['DT_RowId'] = `file-${file.id}`
        filesDataTable.row.add(file).draw()
    }
}

export function addFileTableRowsBatch(files) {
    if (!filesDataTable || !files.length) return
    files.forEach((file) => {
        file['DT_RowId'] = `file-${file.id}`
    })
    // draw(false) avoids DataTables scroll-reset on incremental loads
    filesDataTable.rows.add(files).draw(false)
}

export function addFileTableRows(data) {
    addFileTableRowsBatch(data.files)
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
    if (event.data === 'pong') return
    let data = JSON.parse(event.data)
    if (data.event === 'file-delete') {
        removeFileTableRow(data.id)
    } else if (data.event === 'file-new') {
        addFileTableRow(data)
    } else if (data.event === 'set-file-name') {
        renameFileRow(data)
    }
})

// Varied name-column widths so rows look realistic rather than uniform
const skeletonNameWidths = [130, 165, 210, 145, 180, 195, 120, 155, 200, 140]

export function showTableSkeletons(count = 10) {
    const tbody = document.querySelector('#files-table tbody')
    if (!tbody) return
    tbody.querySelector('.dataTables_empty')?.closest('tr')?.remove()
    const fragment = document.createDocumentFragment()
    const specs = [
        { w: 18, h: 18 },
        { w: 24 },
        { w: 0 }, // name — varied per row, set below
        { w: 58 },
        { w: 78 },
        { w: 112 },
        { w: 14 },
        { w: 14 },
        { w: 14 },
        { w: 28 },
        { w: 18 },
    ]
    for (let i = 0; i < count; i++) {
        const tr = document.createElement('tr')
        tr.className = 'dt-skeleton-row'
        specs.forEach(({ w, h = 14 }, colIndex) => {
            const td = document.createElement('td')
            const cell = document.createElement('div')
            cell.className = 'dt-skeleton-cell'
            const width =
                colIndex === 2
                    ? skeletonNameWidths[i % skeletonNameWidths.length]
                    : w
            cell.style.width = `${width}px`
            cell.style.height = `${h}px`
            td.appendChild(cell)
            tr.appendChild(td)
        })
        fragment.appendChild(tr)
    }
    tbody.appendChild(fragment)
}

// Usually unnecessary — DataTables .draw() clears these — but needed when draw is skipped (empty result set)
export function hideTableSkeletons() {
    document.querySelectorAll('.dt-skeleton-row').forEach((el) => el.remove())
}

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

$('.bulk-private').on('click', bulkPrivate)

export function bulkPrivate(_event) {
    let pks = []
    filesDataTable.rows('.selected').every(function () {
        pks.push(this.data().id)
    })
    socket.send(
        JSON.stringify({ method: 'private_files', pks: pks, private: true })
    )
}

$('.bulk-public').on('click', bulkPublic)

export function bulkPublic(_event) {
    let pks = []
    filesDataTable.rows('.selected').every(function () {
        pks.push(this.data().id)
    })
    socket.send(
        JSON.stringify({ method: 'private_files', pks: pks, private: false })
    )
}
