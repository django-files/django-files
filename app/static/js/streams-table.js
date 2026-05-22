import { socket } from './socket.js'

const streamsTable = $('#streams-table')
const deleteStreamModal = $('#delete-stream-modal')
let pendingDeleteName

export const faKey = document.querySelector('div.d-none > .fa-key')
export const faGlobe = document.querySelector('div.d-none > .fa-globe')
export const faVideo = document.querySelector('div.d-none > .fa-video')
export const faStop = document.querySelector('div.d-none > .fa-stop')
export const faCircle = document.querySelector('div.d-none > .fa-circle')
export const streamLink = document.querySelector('div.d-none > .dj-stream-link')

let streamsDataTable

const dataTablesOptions = {
    paging: false,
    order: [5, 'desc'],
    responsive: {
        details: false,
    },
    saveState: true,
    pageLength: -1,
    lengthMenu: [
        [1, 10, 25, 45, 100, 250, -1],
        [1, 10, 25, 45, 100, 250, 'All'],
    ],
    select: {
        style: 'multi',
        selector: 'td:first-child',
    },
    columns: [
        { data: null },
        { data: 'name' },
        { data: 'title' },
        { data: 'user_name' },
        { data: 'is_live' },
        { data: 'started_at' },
        { data: 'ended_at' },
        { data: 'unique_views' },
        { data: 'password' },
        { data: 'public' },
        { data: null },
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
            width: '150px',
            responsivePriority: 1,
            render: getStreamLink,
            defaultContent: '',
            type: 'html',
        },
        {
            targets: 2,
            responsivePriority: 1,
            defaultContent: '',
            width: '200px',
            render: getStreamTitle,
            type: 'html',
        },
        {
            targets: 3,
            responsivePriority: 3,
            defaultContent: '',
            width: '120px',
        },
        {
            targets: 4,
            responsivePriority: 2,
            render: getLiveStatus,
            defaultContent: '',
            width: '80px',
        },
        {
            name: 'started_at',
            targets: 5,
            render: DataTable.render.datetime('DD MMM YYYY, kk:mm'),
            defaultContent: '',
            responsivePriority: 4,
            width: '150px',
        },
        {
            name: 'ended_at',
            targets: 6,
            render: getEndedAt,
            defaultContent: '',
            responsivePriority: 5,
            width: '150px',
        },
        {
            targets: 7,
            responsivePriority: 6,
            defaultContent: '0',
            width: '80px',
        },
        {
            targets: 8,
            render: getPasswordIcon,
            defaultContent: '',
            responsivePriority: 7,
            width: '50px',
        },
        {
            targets: 9,
            render: getPublicIcon,
            defaultContent: '',
            responsivePriority: 8,
            width: '50px',
        },
        {
            targets: 10,
            orderable: false,
            responsivePriority: 9,
            render: getActions,
            defaultContent: '',
            width: '80px',
        },
    ],
    ajax: {
        url: '/api/streams/',
        dataSrc: 'streams',
    },
    language: {
        emptyTable: '',
        loadingRecords: '',
        zeroRecords: '',
    },
    initComplete: function () {
        const dt = this.api()
        initDtLang(dt, 'No streams available', 'No matching streams found')
        if (dt.rows().count() === 0) dt.draw()

        const container = $(dt.table().container())
        const startCell = container.find('.dt-layout-start').first()
        const endCell = container.find('.dt-layout-end').first()

        const obsButtonContainer = document.getElementById(
            'obs-button-container'
        )
        if (obsButtonContainer) {
            startCell.append(obsButtonContainer)
            obsButtonContainer.classList.remove('d-none')
        }

        const userSelectContainer = document.getElementById(
            'dt-user-select-wrapper'
        )
        if (userSelectContainer) {
            endCell.prepend(userSelectContainer)
            userSelectContainer.classList.remove('d-none')
        }

        requestAnimationFrame(() =>
            requestAnimationFrame(() =>
                document
                    .getElementById('streams-table-section')
                    ?.classList.add('dt-section-ready')
            )
        )
    },
}

function getStreamLink(data, type, row) {
    if (type === 'display') {
        const link = streamLink.cloneNode(true)
        const linkClip = link.querySelector('.dj-stream-link-clip')

        // Set clipboard functionality
        linkClip.setAttribute('data-clipboard-text', row.url)

        // Create and insert the stream name link before the clipboard icon
        const nameLink = document.createElement('a')
        nameLink.href = row.url
        nameLink.className = 'link-body-emphasis me-2'
        nameLink.textContent = row.name

        const span = link.querySelector('span')
        span.insertBefore(nameLink, span.lastChild)

        span.className = 'd-inline-block'

        return link.outerHTML
    }
    return data
}

function getStreamTitle(data, type, row) {
    if (type === 'display') {
        if (row.is_owner) {
            return `<span class="stream-editable rounded-1 text-break d-inline-block align-middle" contenteditable="true" data-stream-name="${row.name}">${data}</span>`
        }
        return `<span class="text-break">${data}</span>`
    }
    return data
}

function getLiveStatus(data, type, _row) {
    if (type === 'display') {
        if (data) {
            return '<span class="badge bg-danger"><i class="fa-solid fa-video me-1"></i>Live</span>'
        } else {
            return '<span class="badge bg-secondary"><i class="fa-solid fa-stop me-1"></i>Offline</span>'
        }
    }
    return data
}

function getEndedAt(data, type, _row) {
    if (type === 'display') {
        if (data) {
            return moment(data).format('DD MMM YYYY, kk:mm')
        } else {
            return '<span class="text-muted">-</span>'
        }
    }
    return data
}

function getPasswordIcon(data, type, _row) {
    if (type === 'display') {
        if (data) {
            return faKey.outerHTML
        } else {
            return '<span class="text-muted">-</span>'
        }
    }
    return data
}

function getPublicIcon(data, type, _row) {
    if (type === 'display') {
        if (data) {
            return faGlobe.outerHTML
        } else {
            return faGlobe.outerHTML.replace('fa-globe', 'fa-lock')
        }
    }
    return data
}

function getActions(data, type, row) {
    if (type === 'display') {
        return `
            <div class="dropdown">
                <button class="btn btn-sm btn-outline-secondary dropdown-toggle" type="button" data-bs-toggle="dropdown" aria-expanded="false">
                    <i class="fa-solid fa-ellipsis-vertical"></i>
                </button>
                <ul class="dropdown-menu">
                    <li><a class="dropdown-item stream-delete-btn link-danger" role="button" data-stream-name="${row.name}">
                        <i class="fa-regular fa-trash-can me-2"></i>Delete
                    </a></li>
                </ul>
            </div>
        `
    }
    return data
}

// Varied widths for name and title columns so skeleton rows look realistic
const _streamSkeletonNameWidths = [110, 140, 95, 155, 120, 145]
const _streamSkeletonTitleWidths = [160, 200, 130, 185, 150, 175]

// Column widths [px] matching the 11 header columns:
// checkbox, name, title, owner, status, started, ended, views, pw, public, actions
const _streamSkeletonSpecs = [
    { w: 18, h: 18 },
    { w: 0 }, // name — varied per row
    { w: 0 }, // title — varied per row
    { w: 80 },
    { w: 58 },
    { w: 112 },
    { w: 112 },
    { w: 28 },
    { w: 14 },
    { w: 14 },
    { w: 38 },
]

function showStreamsSkeletons(count = 10) {
    const tbody = document.querySelector('#streams-table tbody')
    if (!tbody) return
    buildSkeletonRows(tbody, count, _streamSkeletonSpecs, {
        1: _streamSkeletonNameWidths,
        2: _streamSkeletonTitleWidths,
    })
}

document.addEventListener('DOMContentLoaded', domContentLoaded)

function domContentLoaded() {
    streamsDataTable = streamsTable.DataTable(dataTablesOptions)
    showStreamsSkeletons()

    if (document.getElementById('user')) {
        $('#user').on('change', function () {
            const userId = $(this).val()
            let url = '/api/streams/'
            if (userId && userId !== '0') {
                url += `?user=${userId}`
            }
            streamsDataTable.ajax.url(url).load()
        })
    }

    streamsTable.on('focus', '.stream-editable', function () {
        $(this).data('original-title', $(this).text().trim())
    })

    streamsTable.on('blur', '.stream-editable', function () {
        const span = $(this)
        const streamName = span.data('stream-name')
        const originalTitle = span.data('original-title')
        const newTitle = span.text().trim()
        if (newTitle && newTitle !== originalTitle) {
            socket.send(
                JSON.stringify({
                    method: 'set-stream-title',
                    name: streamName,
                    title: newTitle,
                })
            )
        } else if (!newTitle) {
            span.text(originalTitle)
        }
    })

    streamsTable.on('keydown', '.stream-editable', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault()
            $(this).blur()
        } else if (e.key === 'Escape') {
            $(this).text($(this).data('original-title'))
            $(this).blur()
        }
    })

    streamsTable.on('click', '.stream-delete-btn', function () {
        pendingDeleteName = $(this).data('stream-name')
        deleteStreamModal.modal('show')
    })

    $('#stream-delete-confirm').on('click', function () {
        if (!pendingDeleteName) return
        socket.send(
            JSON.stringify({ method: 'delete-stream', name: pendingDeleteName })
        )
        deleteStreamModal.modal('hide')
        pendingDeleteName = null
    })
}

socket?.addEventListener('message', function (event) {
    if (event.data === 'pong') return
    const data = JSON.parse(event.data)
    if (data.event === 'stream-delete') {
        streamsDataTable
            ?.row(function (_idx, rowData) {
                return rowData.name === data.name
            })
            .remove()
            .draw()
    }
})
