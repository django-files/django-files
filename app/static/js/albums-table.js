import { fetchAlbums } from './api-fetch.js'
import { initBulkSelect, selectedPks, wireDeleteModal } from './bulk-actions.js'
import { attachSocketTableSync, socket } from './socket.js'
import {
    noChromeLayout,
    paginatedTableDefaults,
    selectColumn,
    selectColumnDef,
    selectConfig,
} from './table-defaults.js'

const albumsTable = $('#albums-table')
const isHome = !!albumsTable.data('home')
const MAX_HOME_ALBUMS = 10
const deleteAlbumButton = document.querySelector('.delete-album-btn')
const albumLink = document.querySelector('div.d-none > .dj-album-link')
const totalAlbumsCount = document.getElementById('total-albums-count')

let albumsDataTable
let loader
let deleteModal

// Dynamic name truncation — viewport-based, half-slope on the narrow home card.
const truncator = createTruncator(isHome ? 0.02 : 0.04)

document.addEventListener('DOMContentLoaded', domContentLoaded)

const dataTablesOptions = {
    ...paginatedTableDefaults,
    ...(isHome && { layout: noChromeLayout }),
    order: [1, 'desc'],
    select: selectConfig,
    columns: [
        selectColumn,
        { data: 'id' },
        { data: 'name' },
        { data: 'date' },
        { data: 'expr' },
        { data: 'view' },
        { data: 'maxv' },
        { data: 'delete' },
    ],
    columnDefs: [
        selectColumnDef,
        { targets: 1, width: '30px', responsivePriority: 5 },
        {
            targets: 2,
            render: renderAlbumLink,
            defaultContent: '',
            responsivePriority: 1,
        },
        {
            name: 'date',
            targets: 3,
            render: DataTable.render.datetime('DD MMM YYYY, kk:mm'),
            defaultContent: '',
            responsivePriority: 2,
            width: '200px',
        },
        {
            targets: 4,
            width: '30px',
            defaultContent: '',
            className: 'expire-value text-center',
            // Expire column is the lowest-value info; hide it entirely on the
            // home card (narrow col-lg-6), demote heavily on /albums/.
            visible: !isHome,
            responsivePriority: 10,
        },
        {
            targets: [5, 6],
            className: 'text-center',
            width: '30px',
            responsivePriority: 4,
        },
        {
            targets: 7,
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
        initBulkSelect(albumsDataTable)
        $('.bulk-delete').on('click', () =>
            deleteModal.open(selectedPks(albumsDataTable))
        )
        $('.bulk-private').on('click', () =>
            socket.send(
                JSON.stringify({
                    method: 'private_albums',
                    pks: selectedPks(albumsDataTable),
                    private: true,
                })
            )
        )
        $('.bulk-public').on('click', () =>
            socket.send(
                JSON.stringify({
                    method: 'private_albums',
                    pks: selectedPks(albumsDataTable),
                    private: false,
                })
            )
        )
    }
    deleteModal = wireDeleteModal({
        modalId: 'delete-album-modal',
        bodyId: 'delete-album-body',
        confirmId: 'album-delete-confirm',
        entity: 'album',
        onConfirm: (pks) => {
            socket.send(JSON.stringify({ method: 'delete-albums', pks: pks }))
        },
    })
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
        extra: { 'album-update': updateAlbumRow },
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

// Column widths [px] matching the 8 header columns:
// select, id, name, date, expire, views, maxviews, delete
const _albumSkeletonSpecs = [
    { w: 18, h: 18 },
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
        2: _albumSkeletonNameWidths,
    })
}

export function updateAlbumRow(data) {
    if (!albumsDataTable) return
    const row = albumsDataTable.row(`#album-${data.id}`)
    if (!row.node()) return
    const current = row.data() || {}
    row.data({ ...current, ...data })
        .invalidate('data')
        .draw(false)
}

function handleDeleteClick(_event) {
    deleteModal.open([$(this).data('hook-id')])
}
