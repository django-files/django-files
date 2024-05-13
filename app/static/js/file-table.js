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
            responsivePriority: 0,
            render: getFileLink,
            defaultContent: '',
            width: '80px',
        },
        {
            targets: 2,
            render: formatBytes,
            defaultContent: '',
        },
        { targets: 3, defaultContent: '' },
        {
            name: 'date',
            targets: 4,
            render: DataTable.render.datetime('DD MMM YYYY, kk:mm'),
            defaultContent: '',
        },
        {
            targets: 5,
            width: '30px',
            defaultContent: '',
            className: 'expire-value text-center',
        },
        { targets: 6, width: '30px', render: getPwIcon, defaultContent: '' },
        {
            targets: 7,
            width: '30px',
            responsivePriority: 4,
            render: getPrivateIcon,
            defaultContent: '',
        },
        {
            targets: 8,
            width: '30px',
            defaultContent: '',
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

export function initFilesTable() {
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
    fileLinkElem.querySelector('.dj-file-link-clip').clipboardText = row.url
    fileLinkElem.querySelector('.dj-file-link-ref').href = row.url
    if (row.name.length > max_name_length) {
        row.name = row.name.substring(0, max_name_length) + '...'
    }
    fileLinkElem.querySelector('.dj-file-link-ref').textContent = row.name
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

function getContextMenu(data, type, row, meta) {
    const ctxMenu = document.createElement('div')
    const toggle = document.createElement('a')
    toggle.classList.add('link-body-emphasis', 'ctx-menu')
    toggle.setAttribute('role', 'button')
    toggle.dataset.bsToggle = 'dropdown'
    toggle.setAttribute('aria-expanded', 'false')
    toggle.setAttribute(
        'class',
        'btn btn-secondary file-context-dropdown my-0 py-0'
    )
    toggle.innerHTML = '<i class="fa-regular fa-square-caret-down"></i>'
    ctxMenu.appendChild(toggle)

    const menu = getCtxMenu(row)
    ctxMenu.appendChild(menu)
    ctxMenu.classList.add(`ctx-menu-${row.id}`)
    return ctxMenu
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
    try {
        totalFilesCount.textContent = filesDataTable.rows().count()
    } catch (e) {}
}

/**
 * Get Context Menu for File
 * @function getCtxMenu
 * @param {Object} file
 * @return {HTMLElement}
 */
export function getCtxMenu(file) {
    // console.debug('getCtxMenu:', file)

    const menu = document.getElementById('ctx-menu-').cloneNode(true)
    menu.id = `ctx-menu-${file.id}`
    menu.dataset.dataPk = file.id
    menu.dataset.id = file.id

    menu.querySelector('.copy-share-link').dataset.clipboardText = file.url
    menu.querySelector('.copy-raw-link').dataset.clipboardText = file.raw
    menu.querySelector('.open-raw').href = file.raw
    menu.querySelector('a[download=""]').setAttribute('download', file.raw)

    menu.querySelector('.ctx-expire').addEventListener('click', cxtSetExpire)
    menu.querySelector('.ctx-private').addEventListener('click', ctxSetPrivate)
    menu.querySelector('.ctx-password').addEventListener(
        'click',
        ctxSetPassword
    )
    menu.querySelector('.ctx-delete').addEventListener('click', ctxDeleteFile)

    // console.log('menu:', menu)
    return menu
}

export function addDTRow(file) {
    file['DT_RowId'] = `file-${file.id}`
    filesDataTable.row.add(file).draw()
}

export function addFileTableNodes(data) {
    for (const file of data.files) {
        console.log(file)
        addDTRow(file)
    }
}
