import { fetchAlbums } from './api-fetch.js'
import { initBulkSelect, selectedPks, wireDeleteModal } from './bulk-actions.js'
import { attachSocketTableSync, socket } from './socket.js'
import {
    applyTagDelta,
    initBulkTagsModal,
    updateTagSearchBadges,
} from './tag-chips.js'
import {
    dtRevealThead,
    initPopupBtn,
    noChromeLayout,
    paginatedTableDefaults,
    selectColumn,
    selectColumnDef,
    selectConfig,
    syncPopupBtnActive,
} from './table-defaults.js'

const albumsTable = $('#albums-table')
const isHome = !!albumsTable.data('home')
const MAX_HOME_ALBUMS = 10
const albumLink = document.querySelector('div.d-none > .dj-album-link')
const totalAlbumsCount = document.getElementById('total-albums-count')

let albumsDataTable
let loader
let deleteModal

let albumsUserLabel = null
let albumsPrivacyLabel = null

function syncAlbumsFilterBtn() {
    const parts = [albumsPrivacyLabel, albumsUserLabel].filter(Boolean)
    let filterLabel = null
    if (parts.length === 1) filterLabel = parts[0]
    else if (parts.length > 1) filterLabel = 'Filtered'
    syncPopupBtnActive('albums-toolbar-filter-btn', filterLabel)
}

function syncPrivacyState(container, activeVal) {
    container.querySelectorAll('.privacy-filter-opt').forEach((btn) => {
        const on = btn.dataset.privacy === activeVal
        btn.classList.toggle('btn-secondary', on)
        btn.classList.toggle('btn-outline-secondary', !on)
    })
}

// Dynamic name truncation — viewport-based, half-slope on the narrow home card.
const truncator = createTruncator(isHome ? 0.02 : 0.04)

document.addEventListener('DOMContentLoaded', domContentLoaded)

const dataTablesOptions = {
    ...paginatedTableDefaults,
    ...(isHome && { layout: noChromeLayout }),
    order: [2, 'desc'],
    select: selectConfig,
    columns: [
        selectColumn,
        { data: 'name' },
        { data: 'date' },
        { data: 'expr' },
        { data: 'file_count' },
        { data: 'view' },
        { data: 'maxv' },
        { data: 'delete' },
    ],
    columnDefs: [
        selectColumnDef,
        {
            targets: 1,
            render: (data, type, row, meta) => {
                if (type === 'filter') {
                    const tags = Array.isArray(row.tags)
                        ? row.tags.join(' ')
                        : ''
                    return `${data || ''} ${tags}`
                }
                if (type === 'display') {
                    return renderAlbumLink(data, type, row, meta)
                }
                return data || ''
            },
            defaultContent: '',
            responsivePriority: 1,
            className: 'dt-name-col',
        },
        {
            name: 'date',
            targets: 2,
            render: DataTable.render.datetime('DD MMM YYYY, kk:mm'),
            defaultContent: '',
            responsivePriority: 2,
        },
        {
            targets: 3,
            defaultContent: '',
            className: 'expire-value text-center',
            // Expire column is the lowest-value info; hide it entirely on the
            // home card (narrow col-lg-6), demote heavily on /albums/.
            visible: !isHome,
            responsivePriority: 10,
        },
        {
            targets: 4,
            className: 'text-center',
            defaultContent: '0',
            responsivePriority: 3,
        },
        {
            targets: [5, 6],
            className: 'text-center',
            responsivePriority: 4,
        },
        {
            targets: 7,
            orderable: false,
            render: renderActions,
            defaultContent: '',
            className: 'text-center',
            width: '40px',
            responsivePriority: 3,
        },
    ],
}

function updateAlbumTagBadges() {
    if (!albumsDataTable) return
    updateTagSearchBadges(albumsDataTable, '.dj-album-link')
}

async function domContentLoaded() {
    albumsDataTable = albumsTable.DataTable(dataTablesOptions)
    albumsDataTable.on('draw.dt', updateAlbumTagBadges)
    truncator.attach(albumsDataTable)
    loader = createPaginatedLoader(albumsDataTable, {
        fetcher: fetchAlbums,
        listKey: 'albums',
        idPrefix: 'album',
        countEl: totalAlbumsCount,
        maxRows: isHome ? MAX_HOME_ALBUMS : null,
        onOverflow: () =>
            document
                .querySelector('.albums-truncation-warning')
                ?.classList.remove('d-none'),
    })
    if (!isHome) {
        initToolbar('albums-toolbar', albumsDataTable)
        attachInfiniteScroll(albumsDataTable, loader)

        // Restore filter state from URL on init
        const initParams = new URL(location.href).searchParams
        const initUserId = initParams.get('user')
        if (initUserId) {
            const tpl = document.getElementById(
                'albums-toolbar-filter-popup-tpl'
            )
            albumsUserLabel =
                tpl?.content
                    .cloneNode(true)
                    .querySelector(`option[value="${initUserId}"]`)
                    ?.textContent?.trim() ?? 'User'
        }
        const initPrivacy = initParams.get('privacy')
        if (initPrivacy === 'public') albumsPrivacyLabel = 'Public'
        else if (initPrivacy === 'private') albumsPrivacyLabel = 'Private'
        syncAlbumsFilterBtn()

        initPopupBtn(
            'albums-toolbar-filter-btn',
            'albums-toolbar-filter-popup-tpl',
            (body) => {
                body.querySelectorAll('.privacy-filter-opt').forEach((btn) => {
                    btn.addEventListener('click', async () => {
                        const val = btn.dataset.privacy
                        if (val === 'public') albumsPrivacyLabel = 'Public'
                        else if (val === 'private')
                            albumsPrivacyLabel = 'Private'
                        else albumsPrivacyLabel = null
                        syncPrivacyState(body, val)
                        syncAlbumsFilterBtn()
                        const url = new URL(location.href)
                        if (val === 'all') url.searchParams.delete('privacy')
                        else url.searchParams.set('privacy', val)
                        globalThis.history.replaceState({}, null, url.href)
                        loader.reset()
                        albumsDataTable.clear().draw()
                        showAlbumsSkeletons()
                        await loader.load()
                        if (!albumsDataTable.rows().count())
                            albumsDataTable.draw()
                    })
                })
                body.querySelector('#user')?.addEventListener(
                    'change',
                    async function () {
                        const userId = this.value
                        albumsUserLabel = userId
                            ? this.options[this.selectedIndex]?.text
                            : null
                        const url = new URL(location.href)
                        if (userId) url.searchParams.set('user', userId)
                        else url.searchParams.delete('user')
                        globalThis.history.replaceState({}, null, url.href)
                        syncAlbumsFilterBtn()
                        loader.reset()
                        albumsDataTable.clear().draw()
                        showAlbumsSkeletons()
                        await loader.load()
                        if (!albumsDataTable.rows().count())
                            albumsDataTable.draw()
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
        initBulkSelect(albumsDataTable)
        $('.bulk-delete').on('click', () =>
            deleteModal.open(selectedPks(albumsDataTable))
        )
        $('.bulk-private').on('click', () =>
            socket.send(
                JSON.stringify({
                    method: 'private_albums',
                    pks: selectedPks(albumsDataTable),
                    private: true,
                })
            )
        )
        $('.bulk-public').on('click', () =>
            socket.send(
                JSON.stringify({
                    method: 'private_albums',
                    pks: selectedPks(albumsDataTable),
                    private: false,
                })
            )
        )
        const bulkTagsModal = initBulkTagsModal(
            socket,
            'bulk_edit_album_tags',
            'album'
        )
        $('.bulk-tags').on('click', () => {
            if (!bulkTagsModal) return
            const items = []
            albumsDataTable.rows('.selected').every(function () {
                const data = this.data()
                items.push({ pk: data.id, tags: data.tags || [] })
            })
            bulkTagsModal.open(items)
        })
    }
    deleteModal = wireDeleteModal({
        modalId: 'delete-album-modal',
        bodyId: 'delete-album-body',
        confirmId: 'album-delete-confirm',
        entity: 'album',
        onConfirm: (pks) => {
            socket.send(JSON.stringify({ method: 'delete-albums', pks: pks }))
        },
    })
    attachSocketTableSync(albumsDataTable, {
        newEvent: 'album-new',
        deleteEvent: 'album-delete',
        idPrefix: 'album',
        addRow: loader.addRow,
        countEl: totalAlbumsCount,
        maxRows: isHome ? MAX_HOME_ALBUMS : null,
        onOverflow: () =>
            document
                .querySelector('.albums-truncation-warning')
                ?.classList.remove('d-none'),
        extra: {
            'album-update': updateAlbumRow,
            'set-album-tags': updateAlbumTags,
        },
    })
    await initDataTable(
        albumsDataTable,
        showAlbumsSkeletons,
        loader.load,
        isHome
            ? 'Albums will appear here once created.'
            : 'No albums available',
        'No matching albums found'
    )
    dtRevealThead(albumsDataTable)
}

function escapeHtmlAttr(v) {
    return String(v ?? '').replace(
        /[&<>"']/g,
        (c) =>
            ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;',
            })[c]
    )
}

function renderActions(data, type, row, _meta) {
    if (type !== 'display') return data
    const id = escapeHtmlAttr(row.id)
    const isPrivate = !!row.private
    const privateIcon = isPrivate ? 'globe' : 'lock'
    const privateLabel = isPrivate ? 'Make Public' : 'Make Private'
    const hasPassword = !!row.password || !!row.has_password
    const passwordLabel = hasPassword ? 'Change Password' : 'Set Password'
    // Treat missing is_owner (older payloads without the flag) as owner.
    const isOwner = row.is_owner === undefined ? true : !!row.is_owner
    const ownerItems = isOwner
        ? `<li><a class="dropdown-item album-toggle-private-btn" role="button" data-album-id="${id}" data-private="${escapeHtmlAttr(isPrivate)}">
                <i class="fa-solid fa-${privateIcon} me-2"></i>${privateLabel}
            </a></li>
            <li><a class="dropdown-item album-set-password-btn" role="button" data-album-id="${id}" data-has-password="${escapeHtmlAttr(hasPassword)}">
                <i class="fa-solid fa-key me-2"></i>${passwordLabel}
            </a></li>
            <li><a class="dropdown-item album-tags-btn" role="button" data-album-id="${id}" data-album-tags="${escapeHtmlAttr(JSON.stringify(row.tags || []))}">
                <i class="fa-solid fa-tags me-2"></i>Manage Tags
            </a></li>
            <li><hr class="dropdown-divider"></li>`
        : ''
    return `
        <div class="dropdown album-ctx-menu" data-album-id="${id}">
            <input type="hidden" name="current-album-password" value="${escapeHtmlAttr(row.password || '')}">
            <button class="dt-ctx-btn" type="button" data-bs-toggle="dropdown" aria-expanded="false" aria-label="More options">
                <i class="fa-solid fa-ellipsis"></i>
            </button>
            <ul class="dropdown-menu dropdown-menu-end">
                <li><a class="dropdown-item album-copy-link-btn" role="button" data-album-id="${id}" data-album-url="${escapeHtmlAttr(row.url)}">
                    <i class="fa-solid fa-link me-2"></i>Copy Link
                </a></li>
                <li><hr class="dropdown-divider"></li>
                ${ownerItems}
                <li><a class="dropdown-item album-delete-btn link-danger" role="button" data-hook-id="${id}">
                    <i class="fa-regular fa-trash-can me-2"></i>Delete
                </a></li>
            </ul>
        </div>
    `
}

function renderAlbumLink(data, type, row, _meta) {
    const albumLinkElem = albumLink.cloneNode(true)
    albumLinkElem.classList.add(`dj-album-link-${row.id}`)
    albumLinkElem
        .querySelector('.dj-album-link-clip')
        .setAttribute('data-clipboard-text', row.url)
    albumLinkElem.querySelector('.dj-album-link-ref').href = row.url
    albumLinkElem.querySelector('.dj-album-link-ref').ariaLabel = row.name
    const len = truncator.length
    let newName = row.name
    if (row.name.length > len) {
        newName = row.name.substring(0, len - 1) + '…'
    }
    albumLinkElem.querySelector('.dj-album-link-ref').textContent = newName
    return albumLinkElem
}

// Shimmer width as a % of the flexible name slot, cycled per row
const _albumSkeletonNameWidths = [66, 82, 55, 92, 62, 76, 52, 73]

// Column widths [px] matching the 8 header columns:
// select, name, date, expire, file_count, views, maxviews, ctx-btn
const _albumSkeletonSpecs = [
    { w: 18 },
    { w: 0 }, // name — flexible slot, absorbs leftover row width
    { w: 128 },
    { w: 14 },
    { w: 20 },
    { w: 20 },
    { w: 20 },
    { w: 22, h: 30 }, // ctx-btn column — drives row to real row height
]

function showAlbumsSkeletons(count = 10) {
    const tbody = document.querySelector('#albums-table tbody')
    if (!tbody) return
    buildSkeletonRows(tbody, count, _albumSkeletonSpecs, {
        1: _albumSkeletonNameWidths,
    })
}

export function updateAlbumRow(data) {
    if (!albumsDataTable) return
    const row = albumsDataTable.row(`#album-${data.id}`)
    if (!row.node()) return
    const current = row.data() || {}
    row.data({ ...current, ...data })
        .invalidate('data')
        .draw(false)
}

// Merge a set-album-tags broadcast into the row so the ctx-menu's
// data-album-tags payload stays fresh for the next Manage Tags open.
function updateAlbumTags(data) {
    if (!albumsDataTable) return
    const row = albumsDataTable.row(`#album-${data.album_id}`)
    if (!row.node()) return
    const current = row.data() || {}
    row.data({ ...current, tags: applyTagDelta(current.tags || [], data) })
        .invalidate('data')
        .draw(false)
}

// albums-actions.js dispatches this when a ctx-menu Delete is clicked — it
// can't open the modal itself because the wired instance lives in this module.
document.addEventListener('album-ctx-delete', function (e) {
    const pk = e.detail?.pk
    if (pk != null && deleteModal) deleteModal.open([pk])
})
