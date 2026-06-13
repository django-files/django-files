import { socket } from './socket.js'
import { fetchFile } from './api-fetch.js'
import { initAlbumSelector, initBulkAlbumSelector } from './album-selector.js'

// JS for Context Menu

console.debug('LOADING: file-context-menu.js')

const fileExpireModal = $('#fileExpireModal')
const filePasswordModal = $('#filePasswordModal')
const fileDeleteModal = $('#fileDeleteModal')
const fileRenameModal = $('#fileRenameModal')
const fileAlbumModal = $('#fileAlbumModal')
const confirmDelete = $('#confirm-delete')

// these listeners are only used on preview page
// see context menu functions for files-table specific listeners
$('.ctx-expire').on('click', ctxSetExpire)
$('.ctx-private').on('click', ctxSetPrivate)
$('.ctx-password').on('click', ctxSetPassword)
$('.ctx-delete').on('click', ctxDeleteFile)
$('.ctx-rename').on('click', ctxRenameFile)
$('.ctx-album').on('click', ctxAlbumFile)

export const faLockOpen = document.querySelector('div.d-none > .fa-lock-open')

// Expire Form

fileExpireModal.on('shown.bs.modal', function (event) {
    console.debug('fileExpireModal shown.bs.modal:', event)
    $(this).find('input').trigger('focus').trigger('select')
})

$('#modal-expire-form').on('submit', function (event) {
    console.debug('#modal-expire-form: submit:', event)
    event.preventDefault()
    const data = genData($(this), 'set-expr-files')
    data.pks = data.pks.split(',')
    console.debug('data:', data)
    socket.send(JSON.stringify(data))
    fileExpireModal.modal('hide')
    data.pks.forEach((pk) => {
        $(`.ctx-menu[data-id="${pk}"] input[name=current-file-expiration]`).val(
            data.expr
        )
    })
})

// Password Form
// TODO: Cleanup Password Forms

filePasswordModal.on('shown.bs.modal', function (event) {
    console.debug('filePasswordModal: shown.bs.modal:', event)
    $(this).find('input').trigger('focus').trigger('select')
})

$('#modal-password-form').on('submit', function (event) {
    console.debug('#modal-password-form: submit:', event)
    event.preventDefault()
    const data = genData($(this), 'set-password-file')
    console.debug('data:', data)
    socket.send(JSON.stringify(data))
    $(`.ctx-menu[data-id="${data.pk}"] input[name=current-file-password]`).val(
        data.password
    )
    filePasswordModal.modal('hide')
})

// Delete File Form

confirmDelete?.on('click', function (event) {
    // TODO: Handle IF/ELSE Better
    const pks = [$(this).data('pks')]
    console.debug(`#confirm-delete.click: pks[]: ${pks}`, event)
    socket.send(JSON.stringify({ method: 'delete-files', pks: pks }))
    if (window.location.pathname.startsWith('/u/')) {
        window.location.replace('/files')
    } else {
        fileDeleteModal.modal('hide')
    }
})

// Rename Form

fileRenameModal.on('shown.bs.modal', function (event) {
    console.debug('fileRenameModal: shown.bs.modal:', event)
    const input = $(this).find('input').get(0)
    input?.focus()
    const end = input?.value.split('.')[0]?.length || 0
    input?.setSelectionRange(0, end)
})

$('#modal-rename-form').on('submit', function (event) {
    console.debug('#modal-rename-form: submit:', event)
    event.preventDefault()
    const data = genData($(this), 'set-file-name')
    console.debug('data:', data)
    socket.send(JSON.stringify(data))
    fileRenameModal.modal('hide')
    $(`.ctx-menu[data-id="${data.pk}"] input[name=current-file-name]`).val(
        data.name
    )
})

// Event Listeners

export function ctxSetExpire(event) {
    const pk = getPrimaryKey(event)
    const pks = [pk]
    console.debug(`ctxSetExpire: pks: ${pks}`, event)
    fileExpireModal.find('input[name=pks]').val(pks)
    const expire = $(
        `.ctx-menu[data-id="${pk}"] input[name=current-file-expiration]`
    )
    const expireValue = expire.val().toString().trim()
    console.debug(`expireInput: ${expireValue}`)
    $('#expr').val(expireValue)
    $('#fileExpireModal #fileExpireModalLabel').text(`Set File Expiration`)
    $('#fileExpireModal #fileExpireModalBodyText').html(
        `Set the file's expiration.`
    )
    fileExpireModal.modal('show')
}

export function ctxSetPrivate(event) {
    const pk = getPrimaryKey(event)
    console.debug(`ctxSetPrivate: pk: ${pk}`, event)
    socket.send(JSON.stringify({ method: 'toggle-private-file', pk: pk }))
}

export function ctxSetPassword(event) {
    const pk = getPrimaryKey(event)
    console.debug(`ctxSetPassword: pk: ${pk}`, event)
    filePasswordModal.find('input[name=pk]').val(pk)
    const input = $(
        `.ctx-menu[data-id="${pk}"] input[name=current-file-password]`
    )
    const password = input.val().toString().trim()
    console.debug(`password: ${password}`)
    filePasswordModal.find('input[name=password]').val(password)
    filePasswordModal.modal('show')
}

export function ctxDeleteFile(event) {
    const pks = [getPrimaryKey(event)]
    console.debug(`ctxDeleteFile: pks: ${pks}`, event)
    confirmDelete?.data('pks', pks)
    $('#fileDeleteModal #fileDeleteModalLabel').text(`Delete File`)
    $('#fileDeleteModal #fileDeleteModalBody').text(
        `Are you sure you want to delete this file?`
    )
    fileDeleteModal.modal('show')
}

export function ctxRenameFile(event) {
    const pk = getPrimaryKey(event)
    console.debug(`ctxRenameFile: pk: ${pk}`, event)
    fileRenameModal.find('input[name=pk]').val(pk)
    const input = $(`.ctx-menu[data-id="${pk}"] input[name=current-file-name]`)
    const name = input.val().toString().trim()
    fileRenameModal.find('input[name=name]').val(name)
    fileRenameModal.modal('show')
}

export async function ctxAlbumFile(event) {
    const pk = getPrimaryKey(event)
    await openAlbumModal([Number.parseInt(pk)], 'single', 'Manage Albums')
}

let albumModalSocketHandler = null

fileAlbumModal.on('hidden.bs.modal', () => {
    if (albumModalSocketHandler) {
        socket?.removeEventListener('message', albumModalSocketHandler)
        albumModalSocketHandler = null
    }
    document.getElementById('modal-album-badge-ui').classList.add('d-none')
})

const ADD_GROUP_HTML = `
    <span class="badge rounded-pill text-bg-primary addto-album-group">
        <button class="btn p-0 addto-album"><i class="fa-solid fa-plus"></i></button>
        <span class="album-add-container d-none">
            <input class="album-search-input" autocomplete="off" placeholder="Search albums…">
        </span>
    </span>`

function albumBadgeHtml(id, label) {
    return `
        <span class="badge rounded-pill text-bg-primary ps-2 file-album-active" id="album-${id}">
            <a class="text-reset text-decoration-none p-0" href="/files/?view=gallery&album=${id}" title="${label}">${label} </a>
            <button id="remove-album-${id}" class="btn p-0 mt-0 remove-album">
                <i class="fa-solid fa-xmark text-small remove-album"></i>
            </button>
        </span>`
}

/**
 * Open the album picker modal.
 * Single mode renders the badge UI identical to the preview sidebar.
 * Bulk mode renders the same badge UI but for the union of albums across all
 * selected files, showing a count "(n)" on badges where only n of the N
 * selected files are in that album.
 *
 * @param {number[]} pks - File IDs to act on.
 * @param {'single'|'bulk'} mode
 * @param {string} title - Modal header text.
 */
export async function openAlbumModal(
    pks,
    mode = 'single',
    title = 'Manage Albums'
) {
    document.getElementById('fileAlbumModalLabel').textContent = title

    const badgeUi = document.getElementById('modal-album-badge-ui')
    const albumContainer = badgeUi.querySelector('.album-container')

    badgeUi.classList.remove('d-none')
    albumContainer.innerHTML =
        '<span class="spinner-border spinner-border-sm text-secondary ms-1" role="status"></span>'

    fileAlbumModal.modal('show')

    if (mode === 'single') {
        const pk = pks[0]
        albumContainer.id = `albums-file-${pk}`

        const file = await fetchFile(pk)
        document.getElementById('fileAlbumModalLabel').textContent =
            `Albums — ${file.name}`
        const currentAlbums = file.albums_details || []

        albumContainer.innerHTML =
            currentAlbums.map((a) => albumBadgeHtml(a.id, a.name)).join('') +
            ADD_GROUP_HTML

        if (albumModalSocketHandler) {
            socket?.removeEventListener('message', albumModalSocketHandler)
        }
        const handleAlbumBadges = initAlbumSelector(badgeUi, socket)
        albumModalSocketHandler = (event) => {
            if (event.data === 'pong') return
            let data
            try {
                data = JSON.parse(event.data)
            } catch {
                return
            }
            if (
                data.event === 'set-file-albums' &&
                String(data.file_id) === String(pk)
            ) {
                handleAlbumBadges?.(data)
            }
        }
        socket?.addEventListener('message', albumModalSocketHandler)
    } else {
        albumContainer.id = 'albums-file-bulk'

        const files = await Promise.all(pks.map((pk) => fetchFile(pk)))

        const albumMap = {}
        for (const file of files) {
            for (const a of file.albums_details || []) {
                if (!albumMap[a.id])
                    albumMap[a.id] = { id: a.id, name: a.name, count: 0 }
                albumMap[a.id].count++
            }
        }

        const albums = Object.values(albumMap)
        albumContainer.innerHTML =
            albums
                .map((a) => {
                    const label =
                        a.count < pks.length ? `${a.name} (${a.count})` : a.name
                    return albumBadgeHtml(a.id, label)
                })
                .join('') + ADD_GROUP_HTML

        initBulkAlbumSelector(badgeUi, socket, pks)
    }
}

function getPrimaryKey(event) {
    const menu = event.target.closest('div')
    let pk = menu?.dataset?.id
    if (!pk) {
        console.warn('OLD PK QUERY USED')
        pk = $(this).parent().parent().parent().data('pk')
    }
    return pk
}

/**
 * Get Context Menu for File
 * @function getCtxMenuContainer
 * @param {Object} file - File Data
 * @param {String} file.id
 * @param {string} file.name
 * @param {string} file.url
 * @param {string} file.raw
 * @param {string} file.raw_uri
 * @param {string} file.expr
 * @param {string} file.password
 * @param {Boolean} file.private
 * @return {HTMLElement}
 */
export function getCtxMenuContainer(file) {
    // console.debug('getCtxMenu:', file)

    const menu = document.getElementById('ctx-menu-').cloneNode(true)
    menu.id = `ctx-menu-${file.id}`

    menu.dataset.dataPk = file.id
    menu.dataset.id = file.id

    menu.querySelector('.copy-share-link').dataset.clipboardText = file.url
    menu.querySelector('.copy-raw-link').dataset.clipboardText = file.raw
    menu.querySelector('.open-raw').href = file.raw
    let downloadLink = menu.querySelector('a[download=""]')
    downloadLink.setAttribute('download', file.name)
    downloadLink.href = file.raw + '?download=true'
    if (menu.querySelector('.ctx-expire')) {
        // gate adding listeners in case user does not have full context
        menu.querySelector('.ctx-expire').addEventListener(
            'click',
            ctxSetExpire
        )
        menu.querySelector('.ctx-private').addEventListener(
            'click',
            ctxSetPrivate
        )
        menu.querySelector('.ctx-password').addEventListener(
            'click',
            ctxSetPassword
        )
        menu.querySelector('.ctx-delete').addEventListener(
            'click',
            ctxDeleteFile
        )
        menu.querySelector('.ctx-rename').addEventListener(
            'click',
            ctxRenameFile
        )
        menu.querySelector('.ctx-album').addEventListener('click', ctxAlbumFile)
        menu.querySelector("[name='current-file-password']").value =
            file.password
        menu.querySelector("[name='current-file-expiration']").value = file.expr
        menu.querySelector("[name='current-file-name']").value = file.name

        // set private button
        if (file.private) {
            menu.querySelector('.privateText').textContent = 'Make Public'
            const icon = menu.querySelector('.privateIcon')
            icon.classList.remove('fa-lock')
            icon.classList.add('fa-lock-open')
        }
    }
    return menu
}

export function getContextMenu(data, type, row) {
    // This is only called by Datatables to render the context menu, it uses getCtxMenuContainer
    const ctxMenu = document.createElement('div')
    const toggle = document.createElement('button')
    ctxMenu.classList.add('ctx-menu')
    toggle.type = 'button'
    toggle.dataset.bsToggle = 'dropdown'
    toggle.dataset.bsStrategy = 'fixed'
    toggle.setAttribute('aria-expanded', 'false')
    toggle.setAttribute('aria-label', 'More options')
    toggle.className = 'dt-ctx-btn file-context-dropdown'
    toggle.innerHTML = '<i class="fa-solid fa-ellipsis"></i>'
    ctxMenu.appendChild(toggle)

    const menu = getCtxMenuContainer(row)
    ctxMenu.appendChild(menu)

    ctxMenu.classList.add(`ctx-menu-${row.id}`)

    // set private button
    if (row.private) {
        menu.getElementsByClassName('privateIcon')[0].outerHTML =
            faLockOpen.outerHTML
        menu.getElementsByClassName('privateText')[0].innerHTML = ' Make Public'
    }

    return ctxMenu
}

/**
 * Convert Form Object to Object
 * @param {jQuery} form $(this) from on submit event
 * @param {String} method The method key value
 * @return {Object}
 */
function genData(form, method) {
    const data = { method: method }
    for (const element of form.serializeArray()) {
        const name = element['name']
        const value = element['value']
        // console.debug(element)
        if (data[name]) {
            if (Array.isArray(data[name])) {
                data[name].push(value)
            } else {
                data[name] = [data[name], value]
            }
        } else {
            data[name] = value
        }
    }
    return data
}

//////// Socket Event Handlers ////////////
// this is where event handlers SPECIFIC to the context menu go

/**
 * Assign the project to an employee.
 * @param {Object} data - File Data
 * @param {string} data.id
 * @param {string} data.uri
 * @param {string} data.name
 * @param {string} data.raw_uri
 */
function messageFileRename(data) {
    // update hidden name value
    $(`.ctx-menu[data-id="${data.id}"] input[name=current-file-name]`).val(
        data.name
    )
    // handle fixing clipboard copy link text
    let shareLink = document.querySelector(
        `.ctx-menu[data-id="${data.id}"] .copy-share-link`
    )
    let shareLinkURL = new URL(shareLink.getAttribute('data-clipboard-text'))
    shareLinkURL.pathname = data.uri
    shareLink.dataset.clipboardText = shareLinkURL.href
    // handle fixing clipboard copy raw link text
    let copyRawLink = document.querySelector(
        `.ctx-menu[data-id="${data.id}"] .copy-raw-link`
    )
    let rawLinkURL = new URL(copyRawLink.getAttribute('data-clipboard-text'))
    rawLinkURL.pathname = data.raw_uri
    shareLink.dataset.clipboardText = rawLinkURL.href
    // handle download link
    let downloadLink = document.querySelector(
        `.ctx-menu[data-id="${data.id}"] .download-file`
    )
    console.debug('downloadLink.href:', downloadLink.href)
    let downloadFileURL = new URL(downloadLink.href)
    downloadFileURL.pathname = data.raw_uri
    downloadLink.href = downloadFileURL
    downloadLink.setAttribute('download', data.name)
    //handle view Raw
    let rawLink = document.querySelector(
        `.ctx-menu[data-id="${data.id}"] .open-raw`
    )
    let rawURL = new URL(rawLink.href)
    rawURL.pathname = data.raw_uri
    rawLink.href = rawURL
}

socket?.addEventListener('message', function (event) {
    if (event.data === 'pong') return
    let data = JSON.parse(event.data)
    // console.debug(event)
    if (data.event === 'set-file-name') {
        messageFileRename(data)
    }
})

export function initContextMenu(container) {
    const wire = (selector, handler) =>
        container
            .querySelectorAll(selector)
            .forEach((el) => el.addEventListener('click', handler))
    wire('.ctx-expire', ctxSetExpire)
    wire('.ctx-private', ctxSetPrivate)
    wire('.ctx-password', ctxSetPassword)
    wire('.ctx-delete', ctxDeleteFile)
    wire('.ctx-rename', ctxRenameFile)
    wire('.ctx-album', ctxAlbumFile)
}
