import { getContextMenu, openAlbumModal } from './file-context-menu.js'

import { attachSocketTableSync, socket } from './socket.js'
import {
    noChromeLayout,
    selectColumn,
    selectColumnDef,
    selectConfig,
} from './table-defaults.js'

const filesTable = $('#files-table')

export const faLock = document.querySelector('div.d-none > .fa-lock')
export const faKey = document.querySelector('div.d-none > .fa-key')
export const faHourglass = document.querySelector('div.d-none > .fa-hourglass')
export const faCaret = document.querySelector(
    'div.d-none > .fa-square-caret-down'
)
export const fileLink = document.querySelector('div.d-none > .dj-file-link')
export const totalFilesCount = document.getElementById('total-files-count')
const filesViewContainer = document.querySelector('[data-files-view]')
const isMapView = () => filesViewContainer?.dataset.filesView === 'map'

const fileExpireModal = $('#fileExpireModal')
const confirmDelete = $('#confirm-delete')
const fileDeleteModal = $('#fileDeleteModal')

let filesDataTable
const truncator = createTruncator()

const dataTablesOptions = {
    paging: false,
    layout: noChromeLayout,
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
        selectColumn,
        { data: 'id', name: 'id' },
        { data: 'name' },
        { data: 'size' },
        { data: 'mime' },
        { data: 'date' },
        { data: null },
        { data: 'expr' },
        { data: 'password' },
        { data: 'private' },
        { data: 'view' },
    ],
    columnDefs: [
        selectColumnDef,
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
            width: '80px',
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
            render: getExifDate,
            defaultContent: '',
            responsivePriority: 6,
            width: '155px',
            className: 'text-nowrap',
        },
        {
            targets: 7,
            width: '15px',
            defaultContent: '',
            className: 'expire-value text-center',
            responsivePriority: 10,
        },
        {
            targets: 8,
            width: '15px',
            render: getPwIcon,
            defaultContent: '',
            responsivePriority: 4,
        },
        {
            targets: 9,
            width: '15px',
            responsivePriority: 4,
            render: getPrivateIcon,
            defaultContent: '',
        },
        {
            targets: 10,
            width: '15px',
            defaultContent: '',
            responsivePriority: 8,
            className: 'text-center',
        },
        {
            targets: 11,
            orderable: false,
            width: '50px',
            responsivePriority: 3,
            render: getContextMenu,
            defaultContent: '',
            className: 'dt-ctx-menu-col',
        },
    ],
    select: selectConfig,
    language: {
        info: '',
        emptyTable: '',
        loadingRecords: '',
        zeroRecords: '',
    },
    initComplete: function () {
        initDtLang(this.api(), 'No files available', 'No matching files found')
    },
}

export function initFilesTable(search = true, ordering = true, info = true) {
    dataTablesOptions.searching = search
    dataTablesOptions.ordering = ordering
    dataTablesOptions.info = info
    filesDataTable = filesTable.DataTable(dataTablesOptions)
    filesDataTable.on('draw.dt', debounce(dtDraw, 150))
    truncator.attach(filesDataTable)
    attachSocketTableSync(filesDataTable, {
        newEvent: 'file-new',
        deleteEvent: 'file-delete',
        idPrefix: 'file',
        addRow: addFileTableRow,
        countEl: totalFilesCount,
        extra: {
            'set-file-name': renameFileRow,
            'file-update': updateFileRow,
        },
    })
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

    const len = truncator.length
    let newName = row.name
    if (row.name.length > len) {
        newName = row.name.substring(0, len - 5) + '...'
    }
    fileLinkElem.querySelector('.dj-file-link-ref').textContent = newName
    return fileLinkElem
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

const _EXIF_MONTHS = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
]

function getExifDate(_data, type, row) {
    const raw = row.exif?.DateTimeOriginal
    if (!raw) return ''
    if (type === 'sort' || type === 'type') return raw
    const match = raw.match(/^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2})/)
    if (!match) return raw
    const month = _EXIF_MONTHS[Number.parseInt(match[2], 10) - 1]
    return `${Number.parseInt(match[3], 10)} ${month} ${match[1]}, ${match[4]}:${match[5]}`
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
    if (totalFilesCount && !isMapView()) {
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

// Refresh the DataTables row data from a `file-update` payload so the row's
// underlying state matches the backend. invalidate() re-runs column renderers
// (private/password/expire icons, etc.) without re-sorting or redrawing the
// whole table.
export function removeFileTableRow(fileId) {
    if (!filesDataTable) return
    const row = filesDataTable.row(`#file-${fileId}`)
    if (row.node()) {
        row.remove().draw(false)
        if (totalFilesCount && !isMapView())
            totalFilesCount.textContent = filesDataTable.rows().count()
    }
}

export function updateFileRow(data) {
    if (!filesDataTable) return
    const row = filesDataTable.row(`#file-${data.id}`)
    if (!row.node()) return
    const current = row.data() || {}
    row.data({ ...current, ...data })
        .invalidate('data')
        .draw(false)
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

// Varied name-column widths so rows look realistic rather than uniform
const skeletonNameWidths = [130, 165, 210, 145, 180, 195, 120, 155, 200, 140]

const _fileSkeletonSpecs = [
    { w: 18, h: 18 },
    { w: 24 },
    { w: 0 }, // name — varied per row
    { w: 58 },
    { w: 60 },
    { w: 112 },
    { w: 100 },
    { w: 14 },
    { w: 14 },
    { w: 14 },
    { w: 28 },
    { w: 18 },
]

export function showTableSkeletons(count = 10) {
    const tbody = document.querySelector('#files-table tbody')
    if (!tbody) return

    // Remove the default DataTables empty placeholder row, plus any stale
    // skeleton rows from a previous load cycle, so only the current shimmer
    // rows remain while new rows are fetched.
    tbody.querySelectorAll('td.dataTables_empty').forEach((cell) => {
        cell.closest('tr')?.remove()
    })
    tbody.querySelectorAll('.dt-skeleton-row').forEach((el) => el.remove())

    buildSkeletonRows(tbody, count, _fileSkeletonSpecs, {
        2: skeletonNameWidths,
    })
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

$('.bulk-album').on('click', bulkManageAlbums)

export async function bulkManageAlbums(_event) {
    const pks = []
    filesDataTable.rows('.selected').every(function () {
        pks.push(this.data().id)
    })
    const s = pks.length === 1 ? '' : 's'
    await openAlbumModal(
        pks,
        'bulk',
        `Updating albums for ${pks.length} file${s}.`
    )
}
