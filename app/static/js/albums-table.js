import { fetchAlbums } from './api-fetch.js'
import { socket } from './socket.js'

const albumsTable = $('#albums-table')
const deleteAlbumModal = $('#delete-album-modal')
const deleteAlbumButton = document.querySelector('.delete-album-btn')
const albumLink = document.querySelector('div.d-none > .dj-album-link')

document.addEventListener('scroll', throttle(albumScroll))
window.addEventListener('resize', throttle(albumScroll))

let albumsDataTable
let nextPage = 1
let fetchLock = false

let fillInterval

const dataTablesOptions = {
    paging: false,
    order: [0, 'desc'],
    responsive: true,
    processing: true,
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
        { data: 'date'},
        { data: 'expr' },
        { data: 'view' },
        { data: 'maxv' },
        { data: 'delete' },
    ],
    columnDefs: [
        { targets: 0, width: '30px', responsivePriority: 5},
        { targets: 1, render: renderAlbumLink, defaultContent: '', responsivePriority: 1},
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
        { targets: [4, 5], className: 'text-center', width: '30px', responsivePriority: 4},
        { targets: 6, orderable: false, render: renderDeleteBtn, defaultContent: '', className: 'text-center', responsivePriority: 3 },
    ],
}

async function initAlbumsTable() {
    albumsDataTable = albumsTable.DataTable(dataTablesOptions)
    await addAlbumRows()
    fillInterval = setInterval(fillPage, 250)
    window.dispatchEvent(new Event('resize'))
}

function renderDeleteBtn(data, type, row, meta){
    let deleteBtn = deleteAlbumButton.cloneNode(true)
    deleteBtn.setAttribute('data-hook-id', row.id)
    deleteBtn.addEventListener('click', handleDeleteClick)
    return deleteBtn
}

function renderAlbumLink(data, type, row, meta) {
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
    albumLinkElem.querySelector('.dj-album-link-clip').setAttribute('data-clipboard-text', row.url)
    albumLinkElem.querySelector('.dj-album-link-ref').href = row.url
    albumLinkElem.querySelector('.dj-album-link-ref').ariaLabel = row.name
    let newName = row.name
    if (row.name.length > max_name_length) {
        newName = row.name.substring(0, max_name_length) + '...'
    }
    albumLinkElem.querySelector('.dj-album-link-ref').textContent = newName
    return albumLinkElem
}

initAlbumsTable()

async function fillPage() {
    if (nextPage) {
        console.debug(
            'fillPage INTERVAL',
            document.body.clientHeight === document.body.scrollHeight
        )
        if (document.body.clientHeight === document.body.scrollHeight) {
            await addAlbumRows()
        } else {
            clearInterval(fillInterval)
        }
    }
}

/**
 * Album onScroll Callback
 * @function galleryScroll
 * @param {Event} event
 * @param {Number} buffer
 */
async function albumScroll(event, buffer = 600) {
    const maxScrollY = document.body.scrollHeight - window.innerHeight
    console.debug(
        `albumScroll: ${window.scrollY} > ${maxScrollY - buffer}`,
        window.scrollY > maxScrollY - buffer
    )
    if (nextPage && (!maxScrollY || window.scrollY > maxScrollY - buffer)) {
        console.debug('End of Scroll')
        await addAlbumRows()
    }
}

async function addAlbumRows() {
    if (!fetchLock) {
        albumsDataTable.processing(true)
        fetchLock = true
        const data = await fetchAlbums(nextPage)
        // console.debug(data)
        nextPage = data.next
        for (const album of data.albums) {
            addAlbumRow(album)
        }
        albumsDataTable.processing(false)
        fetchLock = false
    }
}

function addAlbumRow(row) {
    row['DT_RowId'] = `album-${row.id}`
    albumsDataTable.row.add(row).draw()
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
        success: function (data) {
            // console.log('data:', data)
            form.trigger('reset')
            // show_toast(`Album Created: ${data.url}`)
        },
        error: messageErrorHandler,
        cache: false,
        contentType: false,
        processData: false,
    })
})


function handleDeleteClick(event) {
    const pk = $(this).data('hook-id')
    $('#album-delete-confirm').data('pk', pk)
    deleteAlbumModal.modal('show')
}

$('#album-delete-confirm').on('click', function (event) {
    const pk = $(this).data('pk')
    socket.send(JSON.stringify({ method: 'delete-album', pk: pk }))
    deleteAlbumModal.modal('hide')
})


socket?.addEventListener('message', function (event) {
    let data = JSON.parse(event.data)
    if (data.event === 'album-delete') {
        $(`#album-${data.id}`).remove()
    } else if (data.event === 'album-new') {
        addAlbumRow(data)
    } 
})
