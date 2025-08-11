import { socket } from './socket.js'

const streamsTable = $('#streams-table')

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
    processing: true,
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
        { data: 'name' },
        { data: 'title' },
        { data: 'user_name' },
        { data: 'is_live' },
        { data: 'started_at' },
        { data: 'ended_at' },
        { data: 'unique_views' },
        { data: 'password' },
        { data: 'public' },
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
}

function getStreamLink(data, type, row) {
    if (type === 'display') {
        const link = streamLink.cloneNode(true)
        const linkRef = link.querySelector('.dj-stream-link-ref')
        const linkClip = link.querySelector('.dj-stream-link-clip')

        linkRef.textContent = data.name
        linkRef.href = row.url

        linkClip.setAttribute('data-clipboard-text', row.url)

        return link.outerHTML
    }
    return data
}

function getLiveStatus(data, type, row) {
    if (type === 'display') {
        if (data) {
            return '<span class="badge bg-danger"><i class="fa-solid fa-video me-1"></i>Live</span>'
        } else {
            return '<span class="badge bg-secondary"><i class="fa-solid fa-stop me-1"></i>Offline</span>'
        }
    }
    return data
}

function getEndedAt(data, type, row) {
    if (type === 'display') {
        if (data) {
            return moment(data).format('DD MMM YYYY, kk:mm')
        } else {
            return '<span class="text-muted">-</span>'
        }
    }
    return data
}

function getPasswordIcon(data, type, row) {
    if (type === 'display') {
        if (data) {
            return faKey.outerHTML
        } else {
            return '<span class="text-muted">-</span>'
        }
    }
    return data
}

function getPublicIcon(data, type, row) {
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
                    <li><a class="dropdown-item" href="${row.url}" target="_blank">
                        <i class="fa-solid fa-external-link-alt me-2"></i>View
                    </a></li>
                    <li><a class="dropdown-item" href="${row.url}" target="_blank">
                        <i class="fa-solid fa-cog me-2"></i>Settings
                    </a></li>
                </ul>
            </div>
        `
    }
    return data
}

// Initialize DataTable
$(document).ready(function () {
    streamsDataTable = streamsTable.DataTable(dataTablesOptions)

    // Handle user filter for superusers
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

    // Handle clipboard functionality
    document.addEventListener('click', function (e) {
        if (e.target.closest('.clip')) {
            const text = e.target
                .closest('.clip')
                .getAttribute('data-clipboard-text')
            if (text) {
                navigator.clipboard.writeText(text).then(() => {
                    // Show success feedback
                    const originalText = e.target.closest('.clip').innerHTML
                    e.target.closest('.clip').innerHTML =
                        '<i class="fa-solid fa-check"></i>'
                    setTimeout(() => {
                        e.target.closest('.clip').innerHTML = originalText
                    }, 1000)
                })
            }
        }
    })
})
