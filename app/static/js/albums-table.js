import { fetchAlbums } from './api-fetch.js'
import { attachSocketTableSync, socket } from './socket.js'
import { noChromeLayout, paginatedTableDefaults } from './table-defaults.js'

const albumsTable = $('#albums-table')
const isHome = !!albumsTable.data('home')
const MAX_HOME_ALBUMS = 10
const deleteAlbumModalEl = document.getElementById('delete-album-modal')
const deleteAlbumModal = deleteAlbumModalEl
    ? bootstrap.Modal.getOrCreateInstance(deleteAlbumModalEl)
    : null
const deleteAlbumButton = document.querySelector('.delete-album-btn')
const albumLink = document.querySelector('div.d-none > .dj-album-link')
const totalAlbumsCount = document.getElementById('total-albums-count')

let albumsDataTable
let loader

// Dynamic name truncation — viewport-based, half-slope on the narrow home card.
const truncator = createTruncator(isHome ? 0.02 : 0.04)

document.addEventListener('DOMContentLoaded', domContentLoaded)

const dataTablesOptions = {
    ...paginatedTableDefaults,
    ...(isHome && { layout: noChromeLayout }),
    columns: [
        { data: 'id' },
        { data: 'name' },
        { data: 'date' },
        { data: 'expr' },
        { data: 'view' },
        { data: 'maxv' },
        { data: 'delete' },
    ],
    columnDefs: [
        { targets: 0, width: '30px', responsivePriority: 5 },
        {
            targets: 1,
            render: renderAlbumLink,
            defaultContent: '',
            responsivePriority: 1,
        },
        {
            name: 'date',
            targets: 2,
            render: DataTable.render.datetime('DD MMM YYYY, kk:mm'),
            defaultContent: '',
            responsivePriority: 2,
            width: '200px',
        },
        {
            targets: 3,
            width: '30px',
            defaultContent: '',
            className: 'expire-value text-center',
            // Expire column is the lowest-value info; hide it entirely on the
            // home card (narrow col-lg-6), demote heavily on /albums/.
            visible: !isHome,
            responsivePriority: 10,
        },
        {
            targets: [4, 5],
            className: 'text-center',
            width: '30px',
            responsivePriority: 4,
        },
        {
            targets: 6,
            orderable: false,
            render: renderDeleteBtn,
            defaultContent: '',
            className: 'text-center',
            responsivePriority: 3,
        },
    ],
}

async function domContentLoaded() {
    albumsDataTable = albumsTable.DataTable(dataTablesOptions)
    truncator.attach(albumsDataTable)
    loader = createPaginatedLoader(albumsDataTable, {
        fetcher: fetchAlbums,
        listKey: 'albums',
        idPrefix: 'album',
        countEl: totalAlbumsCount,
        maxRows: isHome ? MAX_HOME_ALBUMS : null,
        onOverflow: () =>
            document
                .querySelector('.albums-truncation-warning')
                ?.classList.remove('d-none'),
    })
    if (!isHome) {
        initToolbar('albums-toolbar', albumsDataTable)
        attachInfiniteScroll(albumsDataTable, loader)
        attachUserFilter(albumsDataTable, {
            loader,
            skeletonFn: showAlbumsSkeletons,
        })
    }
    attachSocketTableSync(albumsDataTable, {
        newEvent: 'album-new',
        deleteEvent: 'album-delete',
        idPrefix: 'album',
        addRow: loader.addRow,
        countEl: totalAlbumsCount,
        maxRows: isHome ? MAX_HOME_ALBUMS : null,
        onOverflow: () =>
            document
                .querySelector('.albums-truncation-warning')
                ?.classList.remove('d-none'),
    })
    await initDataTable(
        albumsDataTable,
        showAlbumsSkeletons,
        loader.load,
        isHome
            ? 'Albums will appear here once created.'
            : 'No albums available',
        'No matching albums found'
    )
}

function renderDeleteBtn(data, type, row, _meta) {
    let deleteBtn = deleteAlbumButton.cloneNode(true)
    deleteBtn.setAttribute('data-hook-id', row.id)
    deleteBtn.addEventListener('click', handleDeleteClick)
    return deleteBtn
}

function renderAlbumLink(data, type, row, _meta) {
    const albumLinkElem = albumLink.cloneNode(true)
    albumLinkElem.classList.add(`dj-album-link-${row.id}`)
    albumLinkElem
        .querySelector('.dj-album-link-clip')
        .setAttribute('data-clipboard-text', row.url)
    albumLinkElem.querySelector('.dj-album-link-ref').href = row.url
    albumLinkElem.querySelector('.dj-album-link-ref').ariaLabel = row.name
    const len = truncator.length
    let newName = row.name
    if (row.name.length > len) {
        newName = row.name.substring(0, len - 1) + '…'
    }
    albumLinkElem.querySelector('.dj-album-link-ref').textContent = newName
    return albumLinkElem
}

// Varied name-column widths so skeleton rows look realistic
const _albumSkeletonNameWidths = [140, 175, 110, 195, 130, 160, 105, 155]

// Column widths [px] matching the 7 header columns:
// id, name, date, expire, views, maxviews, delete
const _albumSkeletonSpecs = [
    { w: 24 },
    { w: 0 }, // name — varied per row
    { w: 128 },
    { w: 14 },
    { w: 20 },
    { w: 20 },
    { w: 20 },
]

function showAlbumsSkeletons(count = 10) {
    const tbody = document.querySelector('#albums-table tbody')
    if (!tbody) return
    buildSkeletonRows(tbody, count, _albumSkeletonSpecs, {
        1: _albumSkeletonNameWidths,
    })
}

function handleDeleteClick(_event) {
    const pk = $(this).data('hook-id')
    $('#album-delete-confirm').data('pk', pk)
    deleteAlbumModal?.show()
}

$('#album-delete-confirm').on('click', function (_event) {
    const pk = $(this).data('pk')
    socket.send(JSON.stringify({ method: 'delete-album', pk: pk }))
    deleteAlbumModal?.hide()
})
