import { fetchAlbums } from './api-fetch.js'
import { socket } from './socket.js'
import { paginatedTableDefaults } from './table-defaults.js'

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
let nextPage = 1
let fetchLock = false
let params = new URL(document.location.toString()).searchParams

// Same dynamic-truncation pattern as file-table.js: viewport-based char
// count, debounced resize listener that invalidates and redraws.
let albumNameLen = getAlbumNameLen(window.innerWidth)

window.addEventListener(
    'resize',
    debounce(function () {
        albumNameLen = getAlbumNameLen(window.innerWidth)
        if (albumsDataTable) {
            albumsDataTable.rows().invalidate('data').draw(false)
        }
    }, 100),
    { passive: true }
)

function getAlbumNameLen(width) {
    // Home is a half-width dash card, so use a tighter slope.
    return Math.round((isHome ? 0.02 : 0.04) * width + 8)
}

document.addEventListener('DOMContentLoaded', domContentLoaded)
if (!isHome) {
    document.addEventListener('scroll', debounce(scrollHandle))
    window.addEventListener('resize', debounce(scrollHandle))
}

if (!isHome) {
    $('#user').on('change', async function () {
        const userId = $(this).val()
        if (userId) {
            params.set('user', userId)
        } else {
            params.delete('user')
        }
        globalThis.history.replaceState({}, null, '/albums/?' + params)
        nextPage = 1
        fetchLock = false
        if (albumsDataTable) albumsDataTable.clear().draw()
        showAlbumsSkeletons()
        await addAlbumRows()
        if (!albumsDataTable.rows().count()) albumsDataTable.draw()
    })
}

async function scrollHandle(event) {
    await pageScroll(event, nextPage, addAlbumRows)
    albumsDataTable?.columns.adjust().draw()
}

const dataTablesOptions = {
    ...paginatedTableDefaults,
    // Home: no chrome. /albums/: hide DataTable's built-in search ('topEnd')
    // because the shared toolbar already provides one.
    layout: isHome
        ? {
              topStart: null,
              topEnd: null,
              bottomStart: null,
              bottomEnd: null,
          }
        : {
              topStart: null,
              topEnd: null,
          },
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
    if (!isHome) initToolbar('albums-toolbar', albumsDataTable)
    await initDataTable(
        albumsDataTable,
        showAlbumsSkeletons,
        addAlbumRows,
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
    let newName = row.name
    if (row.name.length > albumNameLen) {
        newName = row.name.substring(0, albumNameLen - 1) + '…'
    }
    albumLinkElem.querySelector('.dj-album-link-ref').textContent = newName
    return albumLinkElem
}

async function addAlbumRows() {
    if (fetchLock) return
    // On the home dashboard, only ever fetch the first page and cap at
    // MAX_HOME_ALBUMS rows — the "View All" link goes to /albums/.
    if (isHome && albumsDataTable?.rows().count() >= MAX_HOME_ALBUMS) {
        nextPage = null
        return
    }
    fetchLock = true
    const data = await fetchAlbums(nextPage)
    nextPage = data.next
    let added = 0
    for (const album of data.albums) {
        if (isHome && albumsDataTable.rows().count() >= MAX_HOME_ALBUMS) break
        addAlbumRow(album)
        added += 1
    }
    if (isHome) {
        const overflow = data.albums.length > added || !!data.next
        if (overflow) {
            document
                .querySelector('.albums-truncation-warning')
                ?.classList.remove('d-none')
        }
        nextPage = null
    }
    fetchLock = false
}

function addAlbumRow(row) {
    row['DT_RowId'] = `album-${row.id}`
    albumsDataTable.row.add(row).draw()
    if (totalAlbumsCount)
        totalAlbumsCount.textContent = albumsDataTable.rows().count()
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

socket?.addEventListener('message', function (event) {
    if (event.data === 'pong') return
    let data = JSON.parse(event.data)
    if (data.event === 'album-delete') {
        $(`#album-${data.id}`).remove()
        if (totalAlbumsCount)
            totalAlbumsCount.textContent = albumsDataTable.rows().count()
    } else if (data.event === 'album-new') {
        if (isHome && albumsDataTable.rows().count() >= MAX_HOME_ALBUMS) {
            document
                .querySelector('.albums-truncation-warning')
                ?.classList.remove('d-none')
            return
        }
        addAlbumRow(data)
    }
})
