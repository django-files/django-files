import { fetchShorts } from './api-fetch.js'
import { noChromeLayout, paginatedTableDefaults } from './table-defaults.js'

const shortsTable = $('#shorts-table')
const isHome = !!shortsTable.data('home')
const MAX_HOME_SHORTS = 10
const totalShortsCount = document.getElementById('total-shorts-count')

let shortsDataTable
let loader

// Dynamic URL truncation — viewport-based, half-slope on the narrow home card.
const truncator = createTruncator(isHome ? 0.02 : 0.04)

document.addEventListener('DOMContentLoaded', domContentLoaded)

const dataTablesOptions = {
    ...paginatedTableDefaults,
    ...(isHome && { layout: noChromeLayout }),
    columns: [
        { data: 'id' },
        { data: 'short' },
        { data: 'url' },
        { data: 'views' },
        { data: 'max' },
        { data: null },
    ],
    columnDefs: [
        { targets: 0, visible: false, responsivePriority: 9 },
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
    truncator.attach(shortsDataTable)
    loader = createPaginatedLoader(shortsDataTable, {
        fetcher: fetchShorts,
        listKey: 'shorts',
        idPrefix: 'short',
        countEl: totalShortsCount,
        maxRows: isHome ? MAX_HOME_SHORTS : null,
        onOverflow: () =>
            document
                .querySelector('.shorts-truncation-warning')
                ?.classList.remove('d-none'),
    })
    if (!isHome) {
        initToolbar('shorts-toolbar', shortsDataTable)
        attachInfiniteScroll(shortsDataTable, loader)
        attachUserFilter(shortsDataTable, {
            loader,
            skeletonFn: showShortsSkeletons,
        })
    }
    await initDataTable(
        shortsDataTable,
        showShortsSkeletons,
        loader.load,
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
        const len = truncator.length
        const display =
            data.length > len ? data.substring(0, len - 1) + '…' : data
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
    loader.reset()
    document
        .querySelector('.shorts-truncation-warning')
        ?.classList.add('d-none')
    loader.load()
})

document.addEventListener('short:deleted', function (event) {
    const { id } = event.detail || {}
    if (!id) return
    const row = shortsDataTable.row(`#short-${id}`)
    if (row.node()) row.remove().draw(false)
})
