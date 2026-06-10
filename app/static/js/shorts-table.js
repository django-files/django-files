import { fetchShorts } from './api-fetch.js'
import { paginatedTableDefaults } from './table-defaults.js'

const shortsTable = $('#shorts-table')
const isHome = !!shortsTable.data('home')
const MAX_HOME_SHORTS = 10

let shortsDataTable
let nextPage = 1
let fetchLock = false
const totalShortsCount = document.getElementById('total-shorts-count')

// Same dynamic-truncation pattern as file-table.js: viewport-based char
// count, debounced resize listener that invalidates and redraws.
let urlLen = getUrlLen(window.innerWidth)

document.addEventListener('DOMContentLoaded', domContentLoaded)
if (!isHome) {
    document.addEventListener('scroll', debounce(scrollHandle))
    window.addEventListener('resize', debounce(scrollHandle))
}
window.addEventListener(
    'resize',
    debounce(function () {
        urlLen = getUrlLen(window.innerWidth)
        if (shortsDataTable) {
            shortsDataTable.rows().invalidate('data').draw(false)
        }
    }, 100),
    { passive: true }
)

function getUrlLen(width) {
    // Home is a half-width dash card, so use a tighter slope.
    return Math.round((isHome ? 0.02 : 0.04) * width + 8)
}

async function scrollHandle(event) {
    await pageScroll(event, nextPage, addShortRows)
    shortsDataTable?.columns.adjust().draw()
}

const dataTablesOptions = {
    ...paginatedTableDefaults,
    // Home: no chrome. /shorts/: hide DataTable's built-in search ('topEnd')
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
        { data: 'short' },
        { data: 'url' },
        { data: 'views' },
        { data: 'max' },
        { data: null },
    ],
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
            width: isHome ? '90px' : '120px',
            responsivePriority: 1,
        },
        {
            targets: 2,
            render: renderUrl,
            defaultContent: '',
            // On the narrow home card, drop the URL column before the actions
            // column so the copy/delete buttons stay visible.
            responsivePriority: isHome ? 8 : 2,
        },
        {
            targets: 3,
            className: 'text-center',
            width: '50px',
            defaultContent: '0',
            visible: !isHome,
            responsivePriority: 3,
        },
        {
            targets: 4,
            className: 'text-center',
            width: '50px',
            defaultContent: '-',
            render: (data) => (data && data !== '0' && data !== 0 ? data : '-'),
            visible: !isHome,
            responsivePriority: 4,
        },
        {
            targets: 5,
            orderable: false,
            render: renderActions,
            defaultContent: '',
            className: 'text-center',
            width: isHome ? '70px' : '160px',
            responsivePriority: 2,
        },
    ],
}

async function domContentLoaded() {
    shortsDataTable = shortsTable.DataTable(dataTablesOptions)
    if (!isHome) initToolbar('shorts-toolbar', shortsDataTable)
    await initDataTable(
        shortsDataTable,
        showShortsSkeletons,
        addShortRows,
        isHome
            ? 'Short URLs will appear here once created.'
            : 'No short URLs available',
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
        const display =
            data.length > urlLen ? data.substring(0, urlLen - 1) + '…' : data
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
    if (fetchLock) return
    // On the home dashboard, only ever fetch the first page and cap at
    // MAX_HOME_SHORTS rows — the "View All" link goes to /shorts/.
    if (isHome && shortsDataTable?.rows().count() >= MAX_HOME_SHORTS) {
        nextPage = null
        return
    }
    fetchLock = true
    const data = await fetchShorts(nextPage)
    nextPage = data.next
    let added = 0
    for (const short of data.shorts) {
        if (isHome && shortsDataTable.rows().count() >= MAX_HOME_SHORTS) break
        addShortRow(short)
        added += 1
    }
    if (isHome) {
        const overflow = data.shorts.length > added || !!data.next
        if (overflow) {
            document
                .querySelector('.shorts-truncation-warning')
                ?.classList.remove('d-none')
        }
        nextPage = null
    }
    fetchLock = false
}

function addShortRow(row) {
    row['DT_RowId'] = `short-${row.id}`
    shortsDataTable.row.add(row).draw(false)
    if (totalShortsCount)
        totalShortsCount.textContent = shortsDataTable.rows().count()
}

const _shortSkeletonUrlWidths = isHome
    ? [90, 120, 80, 130, 100, 110]
    : [180, 220, 150, 240, 170, 200]

// Visible columns differ by mode:
// /shorts/: short, url, views, max, actions (id is hidden col 0)
// home:    short, url, actions (views/max also hidden)
const _shortSkeletonSpecs = isHome
    ? [{ w: 60 }, { w: 0 }, { w: 40 }]
    : [{ w: 60 }, { w: 0 }, { w: 24 }, { w: 24 }, { w: 50 }]

function showShortsSkeletons(count = isHome ? MAX_HOME_SHORTS : 8) {
    const tbody = document.querySelector('#shorts-table tbody')
    if (!tbody) return
    buildSkeletonRows(tbody, count, _shortSkeletonSpecs, {
        1: _shortSkeletonUrlWidths,
    })
}

// Create/delete behavior is shared across pages via short-create.js and
// short-delete.js. React to their CustomEvents to keep the DataTable in sync.
document.addEventListener('short:created', function () {
    shortsDataTable.clear().draw()
    nextPage = 1
    fetchLock = false
    document
        .querySelector('.shorts-truncation-warning')
        ?.classList.add('d-none')
    addShortRows()
})

document.addEventListener('short:deleted', function (event) {
    const { id } = event.detail || {}
    if (!id) return
    const row = shortsDataTable.row(`#short-${id}`)
    if (row.node()) row.remove().draw(false)
})

$('#user').on('change', async function () {
    const userId = $(this).val()
    const url = new URL(location.href)
    if (userId) {
        url.searchParams.set('user', userId)
    } else {
        url.searchParams.delete('user')
    }
    globalThis.history.replaceState({}, null, url.href)
    nextPage = 1
    fetchLock = false
    shortsDataTable.clear().draw()
    showShortsSkeletons()
    await addShortRows()
    if (!shortsDataTable.rows().count()) shortsDataTable.draw()
})
