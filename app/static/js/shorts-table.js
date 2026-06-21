import { fetchShorts } from './api-fetch.js'
import { initBulkSelect, selectedPks, wireDeleteModal } from './bulk-actions.js'
import {
    dtRevealThead,
    initPopupBtn,
    noChromeLayout,
    paginatedTableDefaults,
    selectColumn,
    selectColumnDef,
    selectConfig,
    syncPopupBtnActive,
    syncUserFilterBtn,
} from './table-defaults.js'

const shortsTable = $('#shorts-table')
const isHome = !!shortsTable.data('home')
const MAX_HOME_SHORTS = 10
const totalShortsCount = document.getElementById('total-shorts-count')

let shortsDataTable
let loader
let deleteModal

// Dynamic URL truncation — viewport-based, half-slope on the narrow home card.
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
        { data: 'short' },
        { data: 'url' },
        { data: 'views' },
        { data: 'max' },
        { data: null },
    ],
    columnDefs: [
        selectColumnDef,
        { targets: 1, visible: false, responsivePriority: 9 },
        {
            targets: 2,
            render: renderShortLink,
            defaultContent: '',
            width: isHome ? '90px' : '120px',
            responsivePriority: 1,
        },
        {
            targets: 3,
            render: renderUrl,
            defaultContent: '',
            // On the narrow home card, drop the URL column before the actions
            // column so the copy/delete buttons stay visible.
            responsivePriority: isHome ? 8 : 2,
        },
        {
            targets: 4,
            className: 'text-center',
            width: '50px',
            defaultContent: '0',
            visible: !isHome,
            responsivePriority: 3,
        },
        {
            targets: 5,
            className: 'text-center',
            width: '50px',
            defaultContent: '-',
            render: (data) => (data && data !== '0' && data !== 0 ? data : '-'),
            visible: !isHome,
            responsivePriority: 4,
        },
        {
            targets: 6,
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
        syncUserFilterBtn(
            'shorts-toolbar-filter-btn',
            'shorts-toolbar-filter-popup-tpl'
        )
        initPopupBtn(
            'shorts-toolbar-filter-btn',
            'shorts-toolbar-filter-popup-tpl',
            (body) => {
                body.querySelector('#user')?.addEventListener(
                    'change',
                    async function () {
                        const userId = this.value
                        const label = userId
                            ? this.options[this.selectedIndex]?.text
                            : null
                        const url = new URL(location.href)
                        if (userId) url.searchParams.set('user', userId)
                        else url.searchParams.delete('user')
                        globalThis.history.replaceState({}, null, url.href)
                        syncPopupBtnActive('shorts-toolbar-filter-btn', label)
                        loader.reset()
                        shortsDataTable.clear().draw()
                        showShortsSkeletons()
                        await loader.load()
                        if (!shortsDataTable.rows().count())
                            shortsDataTable.draw()
                    }
                )
            },
            {
                prepareContent: (clone) => {
                    const sel = clone.querySelector('#user')
                    if (sel)
                        sel.value =
                            new URL(location.href).searchParams.get('user') ??
                            ''
                },
            }
        )
        initBulkSelect(shortsDataTable)
        $('.bulk-delete').on('click', () =>
            deleteModal.open(selectedPks(shortsDataTable))
        )
    }
    deleteModal = wireDeleteModal({
        modalId: 'delete-short-modal',
        bodyId: 'delete-short-body',
        confirmId: 'short-delete-confirm',
        entity: 'short URL',
        entityPlural: 'short URLs',
        onConfirm: deleteShorts,
    })
    document.addEventListener('click', function (event) {
        const btn = event.target.closest('.delete-short-btn')
        if (!btn) return
        deleteModal.open([Number(btn.dataset.hookId)])
    })
    await initDataTable(
        shortsDataTable,
        showShortsSkeletons,
        loader.load,
        isHome
            ? 'Short URLs will appear here once created.'
            : 'No short URLs available',
        'No matching short URLs found'
    )
    dtRevealThead(shortsDataTable)
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

// Visible columns differ by mode (id is the always-hidden ordering column):
// /shorts/: select, short, url, views, max, actions
// home:    select, short, url, actions (views/max also hidden)
const _shortSkeletonSpecs = isHome
    ? [{ w: 18 }, { w: 60 }, { w: 0 }, { w: 40 }]
    : [{ w: 18 }, { w: 60 }, { w: 0 }, { w: 24 }, { w: 24 }, { w: 50 }]

function showShortsSkeletons(count = isHome ? MAX_HOME_SHORTS : 8) {
    const tbody = document.querySelector('#shorts-table tbody')
    if (!tbody) return
    buildSkeletonRows(tbody, count, _shortSkeletonSpecs, {
        2: _shortSkeletonUrlWidths,
    })
}

function deleteShorts(ids) {
    return new Promise((resolve) => {
        $.ajax({
            type: 'DELETE',
            url: '/api/shorts/delete/',
            data: JSON.stringify({ ids }),
            contentType: 'application/json',
            headers: { 'X-CSRFToken': csrftoken },
            success: function () {
                ids.forEach((id) =>
                    document.dispatchEvent(
                        new CustomEvent('short:deleted', { detail: { id } })
                    )
                )
                show_toast(
                    ids.length === 1
                        ? `Short URL ${ids[0]} Successfully Removed.`
                        : `${ids.length} Short URLs Successfully Removed.`,
                    'success'
                )
                resolve()
            },
            error: function (jqXHR) {
                messageErrorHandler(jqXHR)
                resolve()
            },
        })
    })
}

// Create behavior is shared across pages via short-create.js. React to its
// CustomEvent to keep the DataTable in sync.
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
