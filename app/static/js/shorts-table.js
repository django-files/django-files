import { fetchShorts } from './api-fetch.js'

const shortsTable = $('#shorts-table')
const deleteShortModal = $('#delete-short-modal')

let shortsDataTable
let nextPage = 1
let fetchLock = false
let pendingDeleteId

document.addEventListener('DOMContentLoaded', domContentLoaded)
document.addEventListener('scroll', debounce(scrollHandle))
window.addEventListener('resize', debounce(scrollHandle))

async function scrollHandle(event) {
    await pageScroll(event, nextPage, addShortRows)
    shortsDataTable?.columns.adjust().draw()
}

const dataTablesOptions = {
    paging: false,
    order: [0, 'desc'],
    responsive: true,
    saveState: true,
    searching: true,
    pageLength: -1,
    language: {
        emptyTable: '',
        loadingRecords: '',
        zeroRecords: '',
    },
    lengthMenu: [
        [10, 25, 50, 100, 250, -1],
        [10, 25, 50, 100, 250, 'All'],
    ],
    columns: [
        { data: 'id' },
        { data: 'short' },
        { data: 'url' },
        { data: 'views' },
        { data: 'max' },
        { data: null },
    ],
    initComplete: function () {
        const container = $(this.api().table().container())
        const startCell = container.find('.dt-layout-start').first()
        const endCell = container.find('.dt-layout-end').first()

        startCell.append(
            $(
                '<button class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#create-short-modal"><i class="fa-solid fa-link me-2"></i> New Short</button>'
            )
        )

        const userSelectWrapper = document.getElementById(
            'dt-user-select-wrapper'
        )
        if (userSelectWrapper) {
            endCell.prepend(userSelectWrapper)
            userSelectWrapper.classList.remove('d-none')
        }

        const section = document.getElementById('shorts-table-section')
        if (section) {
            requestAnimationFrame(() =>
                requestAnimationFrame(() =>
                    section.classList.add('dt-section-ready')
                )
            )
        }
    },
    columnDefs: [
        {
            targets: 0,
            visible: false,
            responsivePriority: 9,
        },
        {
            targets: 1,
            render: renderShortLink,
            defaultContent: '',
            responsivePriority: 1,
        },
        {
            targets: 2,
            render: renderUrl,
            defaultContent: '',
            responsivePriority: 2,
        },
        {
            targets: 3,
            className: 'text-center',
            width: '50px',
            defaultContent: '0',
            responsivePriority: 3,
        },
        {
            targets: 4,
            className: 'text-center',
            width: '50px',
            defaultContent: '-',
            render: (data) => (data && data !== '0' && data !== 0 ? data : '-'),
            responsivePriority: 4,
        },
        {
            targets: 5,
            orderable: false,
            render: renderActions,
            defaultContent: '',
            className: 'text-center',
            width: '80px',
            responsivePriority: 3,
        },
    ],
}

async function domContentLoaded() {
    shortsDataTable = shortsTable.DataTable(dataTablesOptions)
    await initDataTable(
        shortsDataTable,
        showShortsSkeletons,
        addShortRows,
        'No short URLs available',
        'No matching short URLs found'
    )
}

function renderShortLink(data, type, row) {
    if (type === 'display') {
        return `<a href="${row.full_url}" class="link-body-emphasis" target="_blank">${data}</a>`
    }
    return data
}

function renderUrl(data, type, _row) {
    if (type === 'display') {
        const maxLen = 60
        const display =
            data.length > maxLen ? data.substring(0, maxLen) + '…' : data
        return `<a href="${data}" target="_blank" class="link-body-emphasis">${display}</a>`
    }
    return data
}

function renderActions(_data, type, row) {
    if (type === 'display') {
        return `<a class="clip text-white mx-1" role="button" data-clipboard-text="${row.full_url}"><i class="fa-regular fa-clipboard"></i></a><a role="button" class="delete-short-btn" data-hook-id="${row.id}" title="Delete"><i class="fa-regular fa-trash-can link-danger"></i></a>`
    }
    return ''
}

async function addShortRows() {
    if (!fetchLock) {
        fetchLock = true
        const data = await fetchShorts(nextPage)
        nextPage = data.next
        for (const short of data.shorts) {
            addShortRow(short)
        }
        fetchLock = false
    }
}

function addShortRow(row) {
    row['DT_RowId'] = `short-${row.id}`
    shortsDataTable.row.add(row).draw(false)
}

const _shortSkeletonUrlWidths = [180, 220, 150, 240, 170, 200]

// Visible columns: short, url, views, max, actions (id is hidden col 0)
const _shortSkeletonSpecs = [
    { w: 60 },
    { w: 0 }, // url — varied per row
    { w: 24 },
    { w: 24 },
    { w: 50 },
]

function showShortsSkeletons(count = 8) {
    const tbody = document.querySelector('#shorts-table tbody')
    if (!tbody) return
    buildSkeletonRows(tbody, count, _shortSkeletonSpecs, {
        1: _shortSkeletonUrlWidths,
    })
}

$('#shortsForm').on('submit', function (event) {
    event.preventDefault()
    const form = $(this)
    submitJsonForm(form, function (resp) {
        form.trigger('reset')
        $('#create-short-modal').modal('hide')
        show_toast(`Short Created: ${resp.url}`, 'success')
        shortsDataTable.clear().draw()
        nextPage = 1
        fetchLock = false
        addShortRows()
    })
})

shortsTable.on('click', '.delete-short-btn', function () {
    pendingDeleteId = $(this).data('hook-id')
    deleteShortModal.modal('show')
})

$('#short-delete-confirm').on('click', function () {
    $.ajax({
        type: 'POST',
        url: `/ajax/delete/short/${pendingDeleteId}/`,
        headers: { 'X-CSRFToken': csrftoken },
        success: function () {
            deleteShortModal.modal('hide')
            const row = shortsDataTable.row(`#short-${pendingDeleteId}`)
            if (row.node()) row.remove().draw(false)
            show_toast(
                `Short URL ${pendingDeleteId} Successfully Removed.`,
                'success'
            )
        },
        error: function (jqXHR) {
            deleteShortModal.modal('hide')
            messageErrorHandler(jqXHR)
        },
        cache: false,
        contentType: false,
        processData: false,
    })
})

if (document.getElementById('user')) {
    $('#user').on('change', function () {
        const userId = $(this).val()
        const url = new URL(location.href)
        if (userId) {
            url.searchParams.set('user', userId)
        } else {
            url.searchParams.delete('user')
        }
        location.href = url.href
    })
}
