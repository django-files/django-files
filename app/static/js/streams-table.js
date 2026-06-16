import { initBulkSelect, selectedPks } from './bulk-actions.js'
import { socket } from './socket.js'
import { openDeleteStreamsModal } from './streams-actions.js'
import {
    initPopupBtn,
    selectColumn,
    selectColumnDef,
    selectConfig,
    syncPopupBtnActive,
} from './table-defaults.js'

const streamsTable = $('#streams-table')

export const faKey = document.querySelector('div.d-none > .fa-key')
export const faGlobe = document.querySelector('div.d-none > .fa-globe')
export const faVideo = document.querySelector('div.d-none > .fa-video')
export const faStop = document.querySelector('div.d-none > .fa-stop')
export const faCircle = document.querySelector('div.d-none > .fa-circle')
export const streamLink = document.querySelector('div.d-none > .dj-stream-link')

let streamsDataTable
let streamsUserLabel = null
let streamsPrivacyLabel = null

function syncStreamsFilterBtn() {
    const parts = [streamsPrivacyLabel, streamsUserLabel].filter(Boolean)
    let filterLabel = null
    if (parts.length === 1) filterLabel = parts[0]
    else if (parts.length > 1) filterLabel = 'Filtered'
    syncPopupBtnActive('streams-toolbar-filter-btn', filterLabel)
}

function syncPrivacyState(container, activeVal) {
    container.querySelectorAll('.privacy-filter-opt').forEach((btn) => {
        const on = btn.dataset.privacy === activeVal
        btn.classList.toggle('btn-secondary', on)
        btn.classList.toggle('btn-outline-secondary', !on)
    })
}

function streamsAjaxUrl() {
    const p = new URL(location.href).searchParams
    const url = new URL('/api/streams/', location.origin)
    const user = p.get('user')
    if (user && user !== '0') url.searchParams.set('user', user)
    const privacy = p.get('privacy')
    if (privacy) url.searchParams.set('privacy', privacy)
    return url.toString()
}

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
    select: selectConfig,
    columns: [
        selectColumn,
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
        selectColumnDef,
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
        if (data) return ''
        return faGlobe.outerHTML.replace('fa-globe', 'fa-lock')
    }
    return data
}

function getActions(data, type, row) {
    if (type === 'display') {
        const publicIcon = row.public ? 'lock' : 'globe'
        const publicLabel = row.public ? 'Make Private' : 'Make Public'
        const ownerItems = row.is_owner
            ? `<li><a class="dropdown-item stream-copy-rtmp-btn" role="button" data-stream-name="${row.name}" data-rtmp-url="${row.rtmp_url || ''}">
                    <i class="fa-solid fa-satellite-dish me-2"></i>Copy RTMP URL
                </a></li>
                <li><a class="dropdown-item stream-rotate-token-btn" role="button" data-stream-name="${row.name}">
                    <i class="fa-solid fa-arrows-rotate me-2"></i>Regenerate Token
                </a></li>
                <li><hr class="dropdown-divider"></li>
                <li><a class="dropdown-item stream-toggle-public-btn" role="button" data-stream-name="${row.name}" data-public="${row.public}">
                    <i class="fa-solid fa-${publicIcon} me-2"></i>${publicLabel}
                </a></li>
                <li><hr class="dropdown-divider"></li>`
            : ''
        return `
            <div class="dropdown">
                <button class="dt-ctx-btn" type="button" data-bs-toggle="dropdown" aria-expanded="false" aria-label="More options">
                    <i class="fa-solid fa-ellipsis"></i>
                </button>
                <ul class="dropdown-menu">
                    ${ownerItems}
                    <li><a class="dropdown-item stream-delete-btn link-danger" role="button" data-hook-id="${row.name}">
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
    initToolbar('streams-toolbar', streamsDataTable)
    initBulkSelect(streamsDataTable)
    // Restore filter state from URL on init
    const initParams = new URL(location.href).searchParams
    const initUserId = initParams.get('user')
    if (initUserId) {
        const tpl = document.getElementById('streams-toolbar-filter-popup-tpl')
        streamsUserLabel =
            tpl?.content
                .cloneNode(true)
                .querySelector(`option[value="${initUserId}"]`)
                ?.textContent?.trim() ?? 'User'
    }
    const initPrivacy = initParams.get('privacy')
    if (initPrivacy === 'public') streamsPrivacyLabel = 'Public'
    else if (initPrivacy === 'private') streamsPrivacyLabel = 'Private'
    syncStreamsFilterBtn()

    initPopupBtn(
        'streams-toolbar-filter-btn',
        'streams-toolbar-filter-popup-tpl',
        (body) => {
            body.querySelectorAll('.privacy-filter-opt').forEach((btn) => {
                btn.addEventListener('click', () => {
                    const val = btn.dataset.privacy
                    if (val === 'public') streamsPrivacyLabel = 'Public'
                    else if (val === 'private') streamsPrivacyLabel = 'Private'
                    else streamsPrivacyLabel = null
                    syncPrivacyState(body, val)
                    syncStreamsFilterBtn()
                    const url = new URL(location.href)
                    if (val === 'all') url.searchParams.delete('privacy')
                    else url.searchParams.set('privacy', val)
                    globalThis.history.replaceState({}, null, url.href)
                    streamsDataTable.ajax.url(streamsAjaxUrl()).load()
                })
            })
            body.querySelector('#user')?.addEventListener(
                'change',
                function () {
                    const userId = this.value
                    streamsUserLabel = userId
                        ? this.options[this.selectedIndex]?.text
                        : null
                    const url = new URL(location.href)
                    if (userId) url.searchParams.set('user', userId)
                    else url.searchParams.delete('user')
                    globalThis.history.replaceState({}, null, url.href)
                    syncStreamsFilterBtn()
                    streamsDataTable.ajax.url(streamsAjaxUrl()).load()
                }
            )
        },
        {
            prepareContent: (clone) => {
                const p = new URL(location.href).searchParams
                syncPrivacyState(clone, p.get('privacy') ?? 'all')
                const sel = clone.querySelector('#user')
                if (sel) sel.value = p.get('user') ?? ''
            },
        }
    )

    const totalStreamsCount = document.getElementById('total-streams-count')
    if (totalStreamsCount) {
        streamsDataTable.on('draw', function () {
            totalStreamsCount.textContent = streamsDataTable
                .rows({ search: 'applied' })
                .count()
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

    $('.bulk-delete').on('click', () =>
        openDeleteStreamsModal(selectedPks(streamsDataTable, 'name'))
    )
    $('.bulk-private').on('click', () =>
        socket.send(
            JSON.stringify({
                method: 'private_streams',
                pks: selectedPks(streamsDataTable, 'name'),
                public: false,
            })
        )
    )
    $('.bulk-public').on('click', () =>
        socket.send(
            JSON.stringify({
                method: 'private_streams',
                pks: selectedPks(streamsDataTable, 'name'),
                public: true,
            })
        )
    )
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
    } else if (data.event === 'toggle-public-stream') {
        data.objects.forEach((obj) => {
            updateStreamRow(obj.name, { public: obj.public })
        })
        streamsDataTable?.draw(false)
    } else if (data.event === 'set-stream-title') {
        if (updateStreamRow(data.name, { title: data.title })) {
            streamsDataTable?.draw(false)
        }
    } else if (data.event === 'set-stream-description') {
        if (updateStreamRow(data.name, { description: data.description })) {
            streamsDataTable?.draw(false)
        }
    }
})

function updateStreamRow(name, patch) {
    const row = streamsDataTable?.row(function (_idx, rowData) {
        return rowData.name === name
    })
    if (!row?.node()) return false
    const rowData = row.data()
    Object.assign(rowData, patch)
    row.data(rowData).invalidate()
    return true
}
