import { fetchAlbums } from './api-fetch.js'
import { socket } from './socket.js'

const albumsTable = $('#albums-table')
const deleteAlbumModal = $('#delete-album-modal')
const deleteAlbumButton = document.querySelector('.delete-album-btn')
const albumLink = document.querySelector('div.d-none > .dj-album-link')

let albumsDataTable
let nextPage = 1
let fetchLock = false

document.addEventListener('DOMContentLoaded', domContentLoaded)
document.addEventListener('scroll', debounce(scrollHandle))
window.addEventListener('resize', debounce(scrollHandle))

async function scrollHandle(event) {
    await pageScroll(event, nextPage, addAlbumRows)
    albumsDataTable?.columns.adjust().draw()
}

const dataTablesOptions = {
    paging: false,
    order: [0, 'desc'],
    responsive: true,
    saveState: true,
    searching: true,
    pageLength: -1,
    lengthMenu: [
        [10, 25, 50, 100, 250, -1],
        [10, 25, 50, 100, 250, 'All'],
    ],
    columns: [
        { data: 'id' },
        { data: 'name' },
        { data: 'date' },
        { data: 'expr' },
        { data: 'view' },
        { data: 'maxv' },
        { data: 'delete' },
    ],
    initComplete: function () {
        const startCell = $(this.api().table().container())
            .find('.dt-layout-start')
            .first()
        startCell.append(
            $(
                '<button class="btn btn-secondary btn-sm" data-bs-toggle="modal" data-bs-target="#create-album-modal"><i class="fa-solid fa-images me-2"></i> New Album</button>'
            )
        )

        // Reveal the section after DataTables has finished all DOM mutations.
        // Double-rAF ensures the browser commits the new layout before
        // opacity transitions to 1, eliminating toolbar-insertion jitter.
        const section = document.getElementById('albums-table-section')
        if (section) {
            requestAnimationFrame(() =>
                requestAnimationFrame(() =>
                    section.classList.add('dt-section-ready')
                )
            )
        }
    },
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
            responsivePriority: 7,
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
    showAlbumsSkeletons()
    await addAlbumRows()
    window.dispatchEvent(new Event('resize'))
}

function renderDeleteBtn(data, type, row, _meta) {
    let deleteBtn = deleteAlbumButton.cloneNode(true)
    deleteBtn.setAttribute('data-hook-id', row.id)
    deleteBtn.addEventListener('click', handleDeleteClick)
    return deleteBtn
}

function renderAlbumLink(data, type, row, _meta) {
    let max_name_length
    if (screen.width < 500) {
        max_name_length = 20
    } else if (screen.width > 500 && screen.width < 1500) {
        max_name_length = 40
    } else {
        max_name_length = 60
    }
    const albumLinkElem = albumLink.cloneNode(true)
    albumLinkElem.classList.add(`dj-album-link-${row.id}`)
    albumLinkElem
        .querySelector('.dj-album-link-clip')
        .setAttribute('data-clipboard-text', row.url)
    albumLinkElem.querySelector('.dj-album-link-ref').href = row.url
    albumLinkElem.querySelector('.dj-album-link-ref').ariaLabel = row.name
    let newName = row.name
    if (row.name.length > max_name_length) {
        newName = row.name.substring(0, max_name_length) + '...'
    }
    albumLinkElem.querySelector('.dj-album-link-ref').textContent = newName
    return albumLinkElem
}

async function addAlbumRows() {
    if (!fetchLock) {
        fetchLock = true
        const data = await fetchAlbums(nextPage)
        // console.debug(data)
        nextPage = data.next
        for (const album of data.albums) {
            addAlbumRow(album)
        }
        fetchLock = false
    }
}

function addAlbumRow(row) {
    row['DT_RowId'] = `album-${row.id}`
    albumsDataTable.row.add(row).draw()
}

// Varied name-column widths so skeleton rows look realistic
const _albumSkeletonNameWidths = [140, 175, 110, 195, 130, 160, 105, 155]

/**
 * Insert count skeleton placeholder rows into the albums table tbody.
 * DataTables clears them automatically on the next .draw() call.
 * @param {number} count
 */
function showAlbumsSkeletons(count = 10) {
    const tbody = document.querySelector('#albums-table tbody')
    if (!tbody) return
    const fragment = document.createDocumentFragment()
    // Column widths [px] matching the 7 header columns:
    // id, name, date, expire, views, maxviews, delete
    const specs = [
        { w: 24 },
        { w: 0 }, // name — varied per row, set below
        { w: 128 },
        { w: 14 },
        { w: 20 },
        { w: 20 },
        { w: 20 },
    ]
    for (let i = 0; i < count; i++) {
        const tr = document.createElement('tr')
        tr.className = 'dt-skeleton-row'
        specs.forEach(({ w, h = 14 }, colIndex) => {
            const td = document.createElement('td')
            const cell = document.createElement('div')
            cell.className = 'dt-skeleton-cell'
            const width =
                colIndex === 1
                    ? _albumSkeletonNameWidths[
                          i % _albumSkeletonNameWidths.length
                      ]
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

// Handle Album FORM Submit
$('#albumsForm').on('submit', function (event) {
    // console.log('#albumsForm submit', event)
    event.preventDefault()
    const form = $(this)
    // console.log('form:', form)
    const data = new FormData(this)
    data.forEach((value, key) => (data[key] = value))
    $.ajax({
        type: form.attr('method'),
        url: form.attr('action'),
        data: JSON.stringify(data),
        headers: { 'X-CSRFToken': csrftoken },
        success: function (_data) {
            form.trigger('reset')
            $('#create-album-modal').modal('hide')
        },
        error: messageErrorHandler,
        cache: false,
        contentType: false,
        processData: false,
    })
})

function handleDeleteClick(_event) {
    const pk = $(this).data('hook-id')
    $('#album-delete-confirm').data('pk', pk)
    deleteAlbumModal.modal('show')
}

$('#album-delete-confirm').on('click', function (_event) {
    const pk = $(this).data('pk')
    socket.send(JSON.stringify({ method: 'delete-album', pk: pk }))
    deleteAlbumModal.modal('hide')
})

socket?.addEventListener('message', function (event) {
    if (event.data === 'pong') return
    let data = JSON.parse(event.data)
    if (data.event === 'album-delete') {
        $(`#album-${data.id}`).remove()
    } else if (data.event === 'album-new') {
        addAlbumRow(data)
    }
})
