// Gallery JS
import {
    initFilesTable,
    faLock,
    faKey,
    faHourglass,
    addFileTableRowsBatch,
    removeFileTableRow,
    formatBytes,
    showTableSkeletons,
    hideTableSkeletons,
} from './file-table.js'

import { updateBulkCount } from './bulk-actions.js'
import { fetchFiles, fetchFile } from './api-fetch.js'
import { initPopupBtn } from './table-defaults.js'

import { socket } from './socket.js'
import { getCtxMenuContainer } from './file-context-menu.js'
import { openPanel } from './file-preview-panel.js'

const galleryContainer = document.getElementById('gallery-container')
const noFilesOverlay = document.getElementById('no-files-overlay')

const imageNode = document.querySelector('div.d-none > img')

let showGallery = document.querySelector('.show-gallery')
if (showGallery) showGallery.onclick = changeView
let showList = document.querySelector('.show-list')
if (showList) showList.onclick = changeView
let showMap = document.querySelector('.show-map')
if (showMap) showMap.onclick = changeView

let params = new URL(document.location.toString()).searchParams

let activeTypes = new Set(
    (params.get('types') || '')
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean)
)

let activeUser = params.get('user') || ''
let activeUserName = ''
let activePrivacy = params.get('privacy') || ''

let nextPage = 1
let fileData = []
let fetchLock = false
let filesDataTable
let selectedFileIds = []
let scrollObserver = null
let gallerySearchTerm = ''
let galleryOrdering = params.get('ordering') || '-created'
let galleryThumbSize = Math.max(
    96,
    Math.min(
        416,
        Number.parseInt(localStorage.getItem('galleryThumbSize') ?? '256', 10)
    )
)
galleryContainer?.style.setProperty(
    '--gallery-thumb-size',
    galleryThumbSize + 'px'
)

let galleryNaturalSizing =
    localStorage.getItem('galleryNaturalSizing') === 'true'
if (galleryNaturalSizing) galleryContainer?.classList.add('gallery-natural')

function getActiveTypesParam() {
    return activeTypes.size > 0 ? [...activeTypes].join(',') : null
}

// Cache touch detection once — isTouchDevice() is called on every hover otherwise
const isTouch =
    'ontouchstart' in window ||
    navigator.maxTouchPoints > 0 ||
    navigator.msMaxTouchPoints > 0

// Cache template element references — avoids repeated querySelector in tight loops
const tmplOuter = document.querySelector('.d-none .gallery-outer')
const tmplInner = document.querySelector('.d-none .gallery-inner')
const tmplIcons = document.querySelector('.d-none .image-icons')
const tmplLabels = document.querySelector('.d-none .image-labels')
const tmplCtx = document.querySelector('.d-none .gallery-ctx')
const tmplCtxToggle = document.querySelector('.d-none button.dt-ctx-btn')
const tmplCheckbox = document.querySelector('.d-none .gallery-checkbox')

function setupScrollObserver() {
    // Map mode has its own dedicated all-pages fetch (fetchAndPlotAllFiles);
    // the table is hidden, so the sentinel sits in-viewport and would loop infinitely.
    if (params.get('view') === 'map') {
        scrollObserver?.disconnect()
        scrollObserver = null
        return
    }
    scrollObserver?.disconnect()
    let sentinel = document.getElementById('load-sentinel')
    if (!sentinel) {
        sentinel = document.createElement('div')
        sentinel.id = 'load-sentinel'
        document.body.appendChild(sentinel)
    }
    // rootMargin = scrollSpace/4 fires early without triggering immediately; recalculate on each call as content grows
    const scrollSpace = Math.max(
        0,
        document.body.scrollHeight - window.innerHeight - window.scrollY
    )
    scrollObserver = new IntersectionObserver(
        ([entry]) => {
            if (entry.isIntersecting && nextPage && !fetchLock) {
                addNodes()
            }
        },
        { rootMargin: `0px 0px ${Math.round(scrollSpace / 4)}px 0px` }
    )
    scrollObserver.observe(sentinel)
}

// Intercept gallery card and table link clicks to open the preview panel
document.addEventListener('click', (e) => {
    // Gallery view: .image-link anchors
    const galleryLink = e.target.closest('.image-link')
    if (galleryLink?.href) {
        e.preventDefault()
        openPanel(galleryLink.href, galleryLink.closest('.gallery-outer'))
        return
    }

    // List view: .dj-file-link-ref anchors inside the files table
    const tableLink = e.target.closest('.dj-file-link-ref')
    if (tableLink?.href && tableLink.closest('#files-table')) {
        e.preventDefault()
        openPanel(tableLink.href)
    }
})

document.addEventListener('DOMContentLoaded', initGallery)

const albumPrivateToggle = document.getElementById('album-private-toggle')
if (albumPrivateToggle) {
    albumPrivateToggle.addEventListener('click', async () => {
        const btn = albumPrivateToggle
        btn.disabled = true
        try {
            const resp = await fetch(btn.dataset.url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken':
                        /csrftoken=([^;]+)/.exec(document.cookie)?.[1] ?? '',
                },
            })
            if (!resp.ok) throw new Error(resp.status)
            const isPrivate = (await resp.text()).trim() === 'True'
            btn.dataset.private = isPrivate ? 'true' : 'false'
            const icon = btn.querySelector('i')
            const label = btn.querySelector('span')
            if (isPrivate) {
                btn.classList.add('files-toolbar-btn--private')
                icon.classList.replace('fa-lock-open', 'fa-lock')
                if (label) label.textContent = 'Private'
                btn.title = 'Private — click to make public'
            } else {
                btn.classList.remove('files-toolbar-btn--private')
                icon.classList.replace('fa-lock', 'fa-lock-open')
                if (label) label.textContent = 'Public'
                btn.title = 'Public — click to make private'
            }
        } catch (e) {
            console.error('Failed to toggle album privacy', e)
        } finally {
            btn.disabled = false
        }
    })
}

function setToolbarBtnVisible(btn, visible) {
    if (!btn) return
    btn.dataset.collapseIntent = visible ? '' : '1'
    if (visible) {
        // No-op if already fully visible (avoids flash on repeated applyView calls)
        if (
            !btn.classList.contains('d-none') &&
            !btn.classList.contains('is-collapsing')
        )
            return
        btn.classList.add('is-collapsing') // collapsed starting point
        btn.classList.remove('d-none') // enter flex layout at width 0
        requestAnimationFrame(() => {
            btn.classList.remove('is-collapsing') // slide + fade in
        })
    } else {
        // No-op if already fully hidden
        if (btn.classList.contains('d-none')) return
        btn.classList.add('is-collapsing') // slide + fade out
        const onEnd = (e) => {
            if (e.propertyName !== 'max-width') return
            btn.removeEventListener('transitionend', onEnd)
            if (btn.dataset.collapseIntent === '1') {
                btn.classList.add('d-none') // remove from flex layout after slide
                btn.classList.remove('is-collapsing')
            }
        }
        btn.addEventListener('transitionend', onEnd)
    }
}

function applyView(view) {
    const container = mapContainer.parentElement
    if (!container) {
        console.error('gallery.js: no container parent')
        return
    }
    // data-files-view drives the CSS that hides the table in gallery/map and
    // stretches the map container; keep map-view-active for the legacy flex sizing.
    container.dataset.filesView = view
    container.classList.toggle('map-view-active', view === 'map')
    galleryContainer.classList.toggle('d-none', view !== 'gallery')
    mapContainer.classList.toggle('d-none', view !== 'map')

    const defaultFooter = document.getElementById('files-footer-default')
    const mapFooter = document.getElementById('files-footer-map')
    defaultFooter?.classList.toggle('d-none', view === 'map')
    mapFooter?.classList.toggle('d-none', view !== 'map')

    for (const link of [showList, showGallery, showMap]) {
        if (link) link.classList.remove('view-active')
    }
    let active
    if (view === 'map') active = showMap
    else if (view === 'gallery') active = showGallery
    else active = showList
    active?.classList.add('view-active')

    setToolbarBtnVisible(
        document.getElementById('gallery-sort-btn'),
        view === 'gallery'
    )
    setToolbarBtnVisible(
        document.getElementById('gallery-size-btn'),
        view === 'gallery'
    )
    setToolbarBtnVisible(
        document.getElementById('gallery-select-all-btn'),
        view === 'gallery'
    )
    setToolbarBtnVisible(
        document.getElementById('map-tracker-btn'),
        view === 'map' && !!params.get('album')
    )
    setToolbarBtnVisible(
        document.getElementById('map-kml-export-btn'),
        view === 'map' && !!params.get('album') && trackerEnabled
    )
}

function detectInitialView() {
    const v = params.get('view')
    if (v === 'map') return 'map'
    if (v === 'gallery') return 'gallery'
    return 'list'
}

function filterGallery() {
    const term = gallerySearchTerm.trim().toLowerCase()
    for (const file of fileData) {
        const card = document.getElementById(`gallery-image-${file.id}`)
        if (!card) continue
        card.classList.toggle(
            'gallery-search-hidden',
            !(!term || file.name.toLowerCase().includes(term))
        )
    }
}

const TYPE_LABELS = {
    image: 'Images',
    video: 'Videos',
    audio: 'Audio',
    document: 'Documents',
    text: 'Text / Code',
    archive: 'Archives',
    executable: 'Executables',
}

function syncFilterBtn() {
    const btn = document.getElementById('files-filter-btn')
    const label = document.getElementById('files-filter-label')
    if (!btn) return
    const typesActive = activeTypes.size > 0
    const userActive = !!activeUser
    const privacyActive = !!activePrivacy
    const active = typesActive || userActive || privacyActive
    btn.classList.toggle('view-active', active)
    if (!label) return
    const activeDimensions = [typesActive, userActive, privacyActive].filter(
        Boolean
    ).length
    if (!active) {
        label.textContent = 'Filter'
    } else if (activeDimensions > 1) {
        label.textContent = 'Filtered'
    } else if (typesActive) {
        label.textContent =
            activeTypes.size === 1
                ? (TYPE_LABELS[[...activeTypes][0]] ?? 'Filter')
                : `${activeTypes.size} types`
    } else if (privacyActive) {
        label.textContent = activePrivacy === 'public' ? 'Public' : 'Private'
    } else {
        label.textContent = activeUserName || 'User'
    }
}

function syncFilterPopoverState(popoverBody) {
    popoverBody.querySelectorAll('.files-filter-opt').forEach((btn) => {
        const t = btn.dataset.type
        const active = t === 'all' ? activeTypes.size === 0 : activeTypes.has(t)
        btn.classList.toggle('btn-secondary', active)
        btn.classList.toggle('btn-outline-secondary', !active)
    })
}

function syncPrivacyState(container, activeVal) {
    container.querySelectorAll('.privacy-filter-opt').forEach((btn) => {
        const on = btn.dataset.privacy === activeVal
        btn.classList.toggle('btn-secondary', on)
        btn.classList.toggle('btn-outline-secondary', !on)
    })
}

async function handleUserChange(userId, userName) {
    activeUser = userId || ''
    activeUserName = userId ? userName || 'User' : ''
    if (userId) {
        params.set('user', userId)
    } else {
        params.delete('user')
    }
    globalThis.history.replaceState({}, null, '/files/?' + params)
    syncFilterBtn()

    fileData = []
    nextPage = 1
    fetchLock = false
    scrollObserver?.disconnect()
    hideSkeletons()
    if (typeof resetSlideshow === 'function') resetSlideshow()
    galleryContainer.replaceChildren()
    if (filesDataTable) filesDataTable.clear().draw()

    const view = params.get('view') || 'list'
    if (view === 'map') {
        if (galleryLeafletMap) {
            galleryLeafletMap.remove()
            galleryLeafletMap = null
            mapInitialised = false
            mapFileMarkers.clear()
        }
        document.getElementById('map-container').innerHTML = ''
        initMapView()
    } else {
        await addNodes()
    }
}

async function resetAndReload() {
    fileData = []
    nextPage = 1
    fetchLock = false
    hideSkeletons()
    galleryContainer.replaceChildren()
    if (filesDataTable) filesDataTable.clear().draw()
    await addNodes()
}

async function applyPrivacyFilter() {
    if (activePrivacy) {
        params.set('privacy', activePrivacy)
    } else {
        params.delete('privacy')
    }
    history.replaceState(null, '', '/files/?' + params)
    syncFilterBtn()
    await resetAndReload()
}

async function applyTypeFilter() {
    const typesStr = [...activeTypes].join(',')
    if (typesStr) {
        params.set('types', typesStr)
    } else {
        params.delete('types')
    }
    history.replaceState(null, '', '/files/?' + params)
    syncFilterBtn()

    await resetAndReload()

    if ((params.get('view') || 'list') === 'map') {
        if (galleryLeafletMap) {
            galleryLeafletMap.remove()
            galleryLeafletMap = null
            mapInitialised = false
            mapFileMarkers.clear()
        }
        document.getElementById('map-container').innerHTML = ''
        initMapView()
    }
}

const SORT_LABELS = {
    '-created': 'Sort',
    created: 'Upload Date',
    name: 'Name',
    '-name': 'Name',
    '-size': 'Size',
    size: 'Size',
    '-exif_date': 'Taken',
    exif_date: 'Taken',
}

function syncSortBtn() {
    const btn = document.getElementById('gallery-sort-btn')
    const label = document.getElementById('gallery-sort-label')
    if (!btn) return
    btn.classList.toggle('view-active', galleryOrdering !== '-created')
    if (label) label.textContent = SORT_LABELS[galleryOrdering] ?? 'Sort'
    const icon = btn.querySelector('i')
    if (icon) {
        const isDesc = galleryOrdering.startsWith('-')
        icon.className = `fa-solid ${isDesc ? 'fa-arrow-down-wide-short' : 'fa-arrow-up-wide-short'}`
    }
}

function syncSortPopoverState(popoverBody) {
    popoverBody.querySelectorAll('[data-ordering]').forEach((btn) => {
        const active = btn.dataset.ordering === galleryOrdering
        btn.classList.toggle('btn-secondary', active)
        btn.classList.toggle('btn-outline-secondary', !active)
    })
}

async function setGalleryOrdering(ordering) {
    if (ordering === galleryOrdering) return
    galleryOrdering = ordering
    params.set('ordering', ordering)
    history.replaceState(null, '', '/files/?' + params)
    syncSortBtn()
    await resetAndReload()
}

function initGallerySelectAllBtn() {
    const btn = document.getElementById('gallery-select-all-btn')
    if (!btn) return

    const icon = btn.querySelector('i')
    const label = btn.querySelector('.files-toolbar-view-label')

    const syncBtn = (allSelected) => {
        btn.setAttribute('aria-pressed', allSelected ? 'true' : 'false')
        btn.classList.toggle('view-active', allSelected)
        if (allSelected) {
            icon.className = 'fa-regular fa-square-minus'
            btn.title = 'Deselect all'
            if (label) label.textContent = 'Deselect all'
        } else {
            icon.className = 'fa-regular fa-square-check'
            btn.title = 'Select all'
            if (label) label.textContent = 'Select all'
        }
    }

    const getVisibleIds = () =>
        fileData
            .filter((f) => {
                const card = document.getElementById(`gallery-image-${f.id}`)
                return card && !card.classList.contains('gallery-search-hidden')
            })
            .map((f) => f.id)

    const isAllSelected = (visibleIds) => {
        const selectedIds = new Set(
            filesDataTable
                .rows('.selected')
                .data()
                .toArray()
                .map((r) => r.id)
        )
        return (
            visibleIds.length > 0 &&
            visibleIds.every((id) => selectedIds.has(id))
        )
    }

    btn.addEventListener('click', () => {
        const visibleIds = getVisibleIds()
        if (isAllSelected(visibleIds)) {
            filesDataTable.rows('.selected').deselect()
            visibleIds.forEach((id) => {
                const cb = document.getElementById(`checkbox-${id}`)
                if (cb) {
                    cb.checked = false
                    cb.classList.add('gallery-mouse')
                    if (!isTouch) cb.classList.add('d-none')
                }
            })
            syncBtn(false)
        } else {
            visibleIds.forEach((id) => {
                filesDataTable.rows(`#file-${id}`).select()
                const cb = document.getElementById(`checkbox-${id}`)
                if (cb) {
                    cb.checked = true
                    cb.classList.remove('gallery-mouse', 'd-none')
                }
            })
            syncBtn(true)
        }
    })

    filesDataTable.on('select deselect', () => {
        const visibleIds = getVisibleIds()
        syncBtn(isAllSelected(visibleIds))
    })
}

async function initGallery() {
    history.scrollRestoration = 'manual'

    // Delegated hover — one listener pair for the whole gallery instead of one per card
    if (galleryContainer) {
        galleryContainer.addEventListener('mouseover', mouseOver)
        galleryContainer.addEventListener('mouseout', mouseOut)

        // Toggle .gallery-ctx-open on container + card for z-index management,
        // replacing the expensive :has() CSS selector
        galleryContainer.addEventListener('show.bs.dropdown', (e) => {
            galleryContainer.classList.add('gallery-ctx-open')
            e.target
                .closest('.gallery-outer')
                ?.classList.add('gallery-ctx-open')
        })
        galleryContainer.addEventListener('hidden.bs.dropdown', (e) => {
            galleryContainer.classList.remove('gallery-ctx-open')
            e.target
                .closest('.gallery-outer')
                ?.classList.remove('gallery-ctx-open')
        })
    }

    filesDataTable = initFilesTable()
    initToolbar('files-toolbar', filesDataTable)
    if (activeUser) {
        const tpl = document.getElementById('files-filter-popup-tpl')
        if (tpl) {
            activeUserName =
                tpl.content
                    .cloneNode(true)
                    .querySelector(`option[value="${activeUser}"]`)
                    ?.textContent?.trim() ?? 'User'
        }
    }
    syncFilterBtn()
    syncSortBtn()

    initPopupBtn(
        'files-filter-btn',
        'files-filter-popup-tpl',
        (tip) => {
            tip.querySelectorAll('.privacy-filter-opt').forEach((optBtn) => {
                optBtn.addEventListener('click', () => {
                    const val = optBtn.dataset.privacy
                    activePrivacy = val === 'all' ? '' : val
                    syncPrivacyState(tip, val)
                    applyPrivacyFilter()
                })
            })
            tip.querySelectorAll('.files-filter-opt').forEach((optBtn) => {
                optBtn.addEventListener('click', () => {
                    const t = optBtn.dataset.type
                    if (t === 'all') activeTypes.clear()
                    else if (activeTypes.has(t)) activeTypes.delete(t)
                    else activeTypes.add(t)
                    syncFilterPopoverState(tip)
                    applyTypeFilter()
                })
            })
            const userSelect = tip.querySelector('#user')
            if (userSelect) {
                userSelect.addEventListener('change', () =>
                    handleUserChange(
                        userSelect.value,
                        userSelect.options[userSelect.selectedIndex]?.text
                    )
                )
            }
        },
        {
            prepareContent: (clone) => {
                syncPrivacyState(clone, activePrivacy || 'all')
                syncFilterPopoverState(clone)
                const userSel = clone.querySelector('#user')
                if (userSel && activeUser) userSel.value = activeUser
            },
        }
    )
    initPopupBtn(
        'gallery-sort-btn',
        'gallery-sort-popup-tpl',
        (tip, popover) => {
            tip.querySelectorAll('[data-ordering]').forEach((optBtn) => {
                optBtn.addEventListener('click', () => {
                    setGalleryOrdering(optBtn.dataset.ordering)
                    popover.hide()
                })
            })
        },
        { prepareContent: syncSortPopoverState }
    )
    initPopupBtn(
        'gallery-size-btn',
        'gallery-size-popup-tpl',
        (tip) => {
            const slider = tip.querySelector('#gallery-size-slider')
            if (slider) {
                slider.addEventListener('input', () => {
                    galleryThumbSize = Number.parseInt(slider.value, 10)
                    localStorage.setItem('galleryThumbSize', galleryThumbSize)
                    galleryContainer.style.setProperty(
                        '--gallery-thumb-size',
                        galleryThumbSize + 'px'
                    )
                })
            }
            const uniformRadio = tip.querySelector('#gallery-sizing-uniform')
            const naturalRadio = tip.querySelector('#gallery-sizing-natural')
            if (uniformRadio && naturalRadio) {
                if (galleryNaturalSizing) naturalRadio.checked = true
                else uniformRadio.checked = true
                tip.addEventListener('change', (e) => {
                    if (!e.target.matches('input[name="gallery-sizing"]'))
                        return
                    galleryNaturalSizing =
                        e.target.id === 'gallery-sizing-natural'
                    localStorage.setItem(
                        'galleryNaturalSizing',
                        galleryNaturalSizing
                    )
                    galleryContainer.classList.add('gallery-mode-switching')
                    setTimeout(() => {
                        galleryContainer.classList.toggle(
                            'gallery-natural',
                            galleryNaturalSizing
                        )
                        galleryContainer.classList.remove(
                            'gallery-mode-switching'
                        )
                    }, 150)
                })
            }
        },
        {
            prepareContent: (clone) => {
                clone.querySelector('#gallery-size-slider').value =
                    galleryThumbSize
            },
        }
    )

    initGallerySelectAllBtn()
    initTrackerBtn()
    initKMLExportBtn()

    // Gallery-view filtering: mirror the search input value into gallerySearchTerm
    // so filterGallery() can apply it when the gallery view is active.
    const searchInput = document.getElementById('files-toolbar-search-input')
    if (searchInput) {
        let filterTimer
        searchInput.addEventListener('input', () => {
            gallerySearchTerm = searchInput.value
            if (params.get('view') === 'gallery') {
                clearTimeout(filterTimer)
                filterTimer = setTimeout(filterGallery, 300)
            }
        })
    }

    const view = detectInitialView()
    applyView(view)
    await addNodes()
    if (view === 'map') initMapView()

    setupScrollObserver()
    filesDataTable.on('select', function (_e, dt, _type, _indexes) {
        const n = filesDataTable.rows({ selected: true }).count()
        const bulkActions = document.getElementById('bulk-actions')
        if (bulkActions) {
            bulkActions.disabled = false
            bulkActions.classList.add('bulk-actions--active')
        }
        updateBulkCount(n)
        let checkbox = document.getElementById(`file-${dt.data().id}`)
        if (checkbox) {
            checkbox.classList.remove('d-none')
        }
    })
    filesDataTable.on('deselect', function (_e, _dt, _type, _indexes) {
        const n = filesDataTable.rows({ selected: true }).count()
        const bulkActions = document.getElementById('bulk-actions')
        if (bulkActions) {
            bulkActions.disabled = n === 0
            bulkActions.classList.toggle('bulk-actions--active', n > 0)
        }
        updateBulkCount(n)
    })
    filesDataTable?.columns.adjust().draw()
}

function showSkeletons() {
    if (!nextPage || gallerySearchTerm.trim()) return

    if (params.get('view') !== 'gallery') {
        showTableSkeletons(40)
        return
    }

    const fragment = new DocumentFragment()
    for (let i = 0; i < 32; i++) {
        const outer = tmplOuter.cloneNode(false)
        outer.id = `gallery-skeleton-${i}`
        outer.classList.add('m-1')

        const inner = tmplInner.cloneNode(false)
        inner.style.aspectRatio = '1 / 1'

        const shimmer = document.createElement('div')
        shimmer.classList.add('img-skeleton')

        inner.appendChild(shimmer)
        outer.appendChild(inner)
        fragment.appendChild(outer)
    }
    galleryContainer.appendChild(fragment)
}

function hideSkeletons() {
    document
        .querySelectorAll('[id^="gallery-skeleton-"]')
        .forEach((el) => el.remove())
    hideTableSkeletons()
}

async function addNodes() {
    if (!nextPage || fetchLock) return

    const atBottom =
        document.body.scrollHeight > window.innerHeight &&
        window.scrollY >= document.body.scrollHeight - window.innerHeight - 5

    fetchLock = true
    showSkeletons()

    const data = await fetchFiles(
        nextPage,
        50,
        params.get('album'),
        galleryOrdering,
        getActiveTypesParam()
    )
    slideshowCallback(data)
    nextPage = data.next
    fileData.push(...data.files)
    hideSkeletons()
    if (params.get('view') === 'gallery') {
        const addedOuters = []
        data.files.forEach((file) => addedOuters.push(addGalleryFile(file)))
        requestAnimationFrame(() => {
            for (const outer of addedOuters) {
                if (outer) outer.classList.remove('gallery-entering')
            }
        })
        filterGallery()
    }
    addFileTableRowsBatch(data.files)
    fetchLock = false
    updateNoFilesOverlay()

    if (atBottom && nextPage) {
        window.scrollTo({
            top: document.body.scrollHeight - window.innerHeight,
            behavior: 'instant',
        })
    }
    if (nextPage) setupScrollObserver()
}

const imageExtensions = /\.(gif|ico|jpeg|jpg|png|webp|jxl|avif)$/i

function addGalleryFile(file, top = false) {
    if (file.mime?.startsWith('video/')) {
        return addGalleryVideo(file, top)
    } else if (imageExtensions.test(file.name)) {
        return addGalleryImage(file, top)
    } else {
        return addGalleryGeneric(file, top)
    }
}

function buildGalleryCard(file, top = false) {
    const outer = tmplOuter.cloneNode(false)
    outer.id = `gallery-image-${file.id}`

    const inner = tmplInner.cloneNode(true)
    outer.appendChild(inner)

    const topLeft = tmplIcons.cloneNode(true)
    const privateStatus = faLock.cloneNode(true)
    privateStatus.classList.add('privateStatus')
    if (!file.private) privateStatus.style.visibility = 'hidden'
    topLeft.appendChild(privateStatus)
    const passwordIcon = faKey.cloneNode(true)
    passwordIcon.classList.add('passwordStatus')
    if (!file.password) passwordIcon.style.visibility = 'hidden'
    topLeft.appendChild(passwordIcon)
    const expireIcon = faHourglass.cloneNode(true)
    if (!file.expr) {
        expireIcon.style.visibility = 'hidden'
    } else {
        expireIcon.title = file.expr
    }
    topLeft.appendChild(expireIcon)
    inner.appendChild(topLeft)

    const bottomLeft = tmplLabels.cloneNode(true)
    buildImageLabels(file, bottomLeft)
    inner.appendChild(bottomLeft)

    const ctxMenu = tmplCtx.cloneNode(true)
    const toggle = tmplCtxToggle.cloneNode(true)
    ctxMenu.appendChild(toggle)
    outer.appendChild(ctxMenu)

    // Lazy: create the full menu DOM only on first open — Bootstrap needs the
    // .dropdown-menu shell immediately for positioning, but the <li> items
    // can wait until the user actually opens the menu.
    const menuShell = document.createElement('div')
    menuShell.id = `ctx-menu-${file.id}`
    menuShell.dataset.id = file.id
    menuShell.dataset.dataPk = file.id
    menuShell.className = 'dropdown fileContextDropdown ctx-menu'
    menuShell.style.zIndex = '1'
    const menuUl = document.createElement('ul')
    menuUl.className = 'dropdown-menu file-context-dropdown-menu'
    menuShell.appendChild(menuUl)
    ctxMenu.appendChild(menuShell)

    toggle.addEventListener(
        'show.bs.dropdown',
        () => {
            if (menuUl.dataset.built) return
            menuUl.dataset.built = '1'
            const full = getCtxMenuContainer(file)
            const fullUl = full.querySelector('ul.dropdown-menu')
            while (fullUl.firstChild) menuUl.appendChild(fullUl.firstChild)
        },
        { once: false }
    )

    inner.appendChild(buildGalleryCheckbox(file))

    // Cache .gallery-mouse elements to avoid querySelectorAll on every hover
    outer._mouseEls = [...outer.querySelectorAll('.gallery-mouse')]

    outer.classList.add('gallery-entering')
    if (top) {
        galleryContainer.insertBefore(outer, galleryContainer.firstChild)
    } else {
        galleryContainer.appendChild(outer)
    }

    return { outer, inner }
}

function showLabelsAlways(outer) {
    const labels = outer.querySelector('.image-labels')
    if (!labels) return
    labels.classList.remove('gallery-mouse', 'd-none')
    if (outer._mouseEls)
        outer._mouseEls = outer._mouseEls.filter((el) => el !== labels)
}

function getFileTypeIcon(mime) {
    if (!mime) return 'fa-file'
    if (mime.startsWith('image/')) return 'fa-file-image'
    if (mime.startsWith('video/')) return 'fa-file-video'
    if (mime.startsWith('audio/')) return 'fa-file-audio'
    if (mime.startsWith('text/')) return 'fa-file-lines'
    if (mime === 'application/pdf') return 'fa-file-pdf'
    if (
        mime.includes('zip') ||
        mime.includes('archive') ||
        mime.includes('tar') ||
        mime.includes('gzip')
    )
        return 'fa-file-zipper'
    if (mime.includes('word') || mime.includes('document'))
        return 'fa-file-word'
    if (mime.includes('excel') || mime.includes('spreadsheet'))
        return 'fa-file-excel'
    if (mime.includes('powerpoint') || mime.includes('presentation'))
        return 'fa-file-powerpoint'
    return 'fa-file'
}

function buildNoThumbPlaceholder(mime) {
    const el = document.createElement('div')
    el.className = 'gallery-no-thumb'
    el.innerHTML = `<i class="fa-solid ${getFileTypeIcon(mime)}"></i>`
    return el
}

function addGalleryGeneric(file, top = false) {
    const { outer, inner } = buildGalleryCard(file, top)

    inner.style.aspectRatio = '1 / 1'

    const link = document.createElement('a')
    link.classList.add('image-link')
    link.href = file.url
    link.title = file.name
    link.target = '_blank'
    link.style.cssText = 'position:absolute;inset:0;display:block'

    link.appendChild(buildNoThumbPlaceholder(file.mime))
    inner.prepend(link)
    showLabelsAlways(outer)
    return outer
}

function addGalleryImage(file, top = false) {
    const { outer, inner } = buildGalleryCard(file, top)

    // IMAGE AND LINK
    const link = document.createElement('a')
    link.classList.add('image-link')
    link.href = file.url
    link.title = file.name
    link.target = '_blank'
    const img = imageNode.cloneNode(true)

    if (file.meta?.PILImageWidth && file.meta?.PILImageHeight) {
        img.width = galleryThumbSize
        img.height = Math.round(
            galleryThumbSize *
                (file.meta.PILImageHeight / file.meta.PILImageWidth)
        )
    } else {
        img.width = galleryThumbSize
        img.height = galleryThumbSize
    }

    const skeleton = document.createElement('div')
    skeleton.classList.add('img-skeleton')
    img.addEventListener(
        'load',
        () => {
            skeleton.style.transition = 'opacity 0.3s'
            skeleton.style.opacity = '0'
            skeleton.addEventListener(
                'transitionend',
                () => skeleton.remove(),
                { once: true }
            )
        },
        { once: true }
    )
    img.addEventListener(
        'error',
        () => {
            skeleton.remove()
            img.style.display = 'none'
            inner.style.aspectRatio = '1 / 1'
            link.appendChild(buildNoThumbPlaceholder(file.mime))
            link.style.cssText = 'position:absolute;inset:0;display:block'
            showLabelsAlways(outer)
        },
        { once: true }
    )

    img.src = file.thumb || file.raw
    link.appendChild(img)
    inner.prepend(skeleton, link)
    return outer
}

function fadeOutSkeleton(skeleton) {
    skeleton.style.transition = 'opacity 0.3s'
    skeleton.style.opacity = '0'
    skeleton.addEventListener('transitionend', () => skeleton.remove(), {
        once: true,
    })
}

function revealVideoThumb(src, img, skeleton) {
    img.onload = () => {
        img.style.visibility = ''
        fadeOutSkeleton(skeleton)
    }
    img.src = src
}

function showVideoThumbError(skeleton, inner, mime) {
    skeleton.remove()
    inner.appendChild(buildNoThumbPlaceholder(mime))
    showLabelsAlways(inner.parentElement)
}

/**
 * Poll a thumbnail URL until the server returns an image Content-Type,
 * meaning the Celery thumb task has finished. Then set the visible img src
 * and fade the skeleton out. Falls back to a static icon after exhausting
 * retries.
 */
function pollVideoThumb(
    src,
    img,
    skeleton,
    inner,
    mime,
    retries = 10,
    delay = 1000
) {
    const maxDelay = 30000
    const retry = () => {
        if (retries > 0) {
            pollVideoThumb(
                src,
                img,
                skeleton,
                inner,
                mime,
                retries - 1,
                Math.min(delay * 2, maxDelay)
            )
        } else {
            showVideoThumbError(skeleton, inner, mime)
        }
    }

    const handleResponse = (res) => {
        if (res.ok && res.headers.get('Content-Type')?.startsWith('image/')) {
            revealVideoThumb(src, img, skeleton)
        } else {
            retry()
        }
    }
    setTimeout(() => {
        // Accept header is set to match what an <img> element sends, so the
        // browser's cache treats this fetch and the subsequent img.src as the
        // same entry (some caches/CDNs vary on Accept).
        fetch(src, {
            method: 'GET',
            credentials: 'omit',
            headers: {
                Accept: 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            },
        })
            .then(handleResponse)
            .catch(retry)
    }, delay)
}

function addGalleryVideo(file, top = false) {
    const { outer, inner } = buildGalleryCard(file, top)

    const link = document.createElement('a')
    link.classList.add('image-link')
    link.href = file.url
    link.title = file.name
    link.target = '_blank'

    const playBtn = document.createElement('div')
    playBtn.classList.add(
        'video-play-overlay',
        'd-flex',
        'align-items-center',
        'justify-content-center'
    )
    playBtn.innerHTML =
        '<i class="fa-solid fa-circle-play fa-3x text-white"></i>'

    // hidden img is the in-flow spacer giving gallery-inner its height; skeleton shimmer sits above it
    const img = imageNode.cloneNode(true)
    // CORS mode so img and pollVideoThumb's fetch share one HTTP cache entry,
    // avoiding a second download when img.src is set after the poll succeeds.
    img.crossOrigin = 'anonymous'
    img.width = galleryThumbSize
    img.height = galleryThumbSize
    img.style.visibility = 'hidden'

    const skeleton = document.createElement('div')
    skeleton.classList.add('img-skeleton')

    link.appendChild(img)
    // prepend order: link(in-flow) at base, skeleton(abs) covers it, playBtn(abs) on top
    inner.prepend(playBtn, skeleton, link)

    if (file.thumb) {
        pollVideoThumb(file.thumb, img, skeleton, inner, file.mime)
    } else {
        showVideoThumbError(skeleton, inner, file.mime)
    }
    return outer
}

function buildGalleryCheckbox(file) {
    const checkbox = tmplCheckbox.cloneNode(true)
    if (isTouch) {
        checkbox.classList.remove('d-none')
    }
    checkbox.id = `checkbox-${file.id}`
    if (selectedFileIds.includes(file.id)) {
        checkbox.checked = true
        checkbox.classList.remove('gallery-mouse', 'd-none')
    } else {
        checkbox.checked = false
    }
    checkbox.addEventListener('click', function () {
        if (this.checked) {
            filesDataTable.rows(`#file-${file.id}`).select()
            this.classList.remove('gallery-mouse')
        } else {
            filesDataTable.rows(`#file-${file.id}`).deselect()
            this.classList.add('gallery-mouse')
            if (!isTouch) this.classList.add('d-none')
        }
    })
    return checkbox
}

function addSpan(parent, textContent) {
    let span = document.createElement('span')
    span.textContent = textContent
    parent.appendChild(span)
    parent.appendChild(document.createElement('br'))
}

function mouseOver(event) {
    if (isTouch) return
    const outer = event.target.closest('.gallery-outer')
    if (!outer || outer.contains(event.relatedTarget)) return
    outer._mouseEls?.forEach((el) => el.classList.remove('d-none'))
}

function mouseOut(event) {
    if (isTouch) return
    const outer = event.target.closest('.gallery-outer')
    if (!outer || outer.contains(event.relatedTarget)) return
    outer._mouseEls?.forEach((el) => {
        if (el.classList.contains('gallery-checkbox') && el.checked) return
        el.classList.add('d-none')
    })
}

// Yields to the browser between batches so painting is incremental rather than a single blocking call
function renderGalleryChunked(files, chunkSize = 20, onComplete = null) {
    let i = 0
    function renderNext() {
        const end = Math.min(i + chunkSize, files.length)
        const chunkOuters = []
        while (i < end) {
            const outer = addGalleryFile(files[i++])
            if (outer) chunkOuters.push(outer)
        }
        requestAnimationFrame(() => {
            for (const outer of chunkOuters)
                outer.classList.remove('gallery-entering')
            if (i < files.length) {
                requestAnimationFrame(renderNext)
            } else if (onComplete) {
                onComplete()
            }
        })
    }
    requestAnimationFrame(renderNext)
}

function syncViewCount(view) {
    const countEl = document.getElementById('total-files-count')
    if (!countEl) return
    if (view === 'map') {
        countEl.textContent = mapFileMarkers.size
    } else {
        countEl.textContent = filesDataTable?.rows().count() ?? 0
    }
}

function changeView(event) {
    event.preventDefault()
    hideSkeletons()
    const view = event.currentTarget.dataset.view || 'list'

    if (view === 'list') {
        params.delete('view')
    } else if (view === 'gallery') {
        params.set('view', 'gallery')
        // Capture selection so the gallery rebuild preserves checked boxes
        selectedFileIds = []
        filesDataTable.rows('.selected').every(function () {
            selectedFileIds.push(this.data().id)
        })
    } else {
        params.set('view', view)
    }
    const newPath = '/files/?' + params

    applyView(view)
    globalThis.history.replaceState({}, null, newPath)
    syncViewCount(view)

    if (view === 'list') {
        galleryContainer.replaceChildren()
        filesDataTable.responsive.recalc()
        setupScrollObserver()
    } else if (view === 'map') {
        initMapView()
    } else {
        // Disconnect before clearing so the sentinel doesn't fire mid-rebuild
        scrollObserver?.disconnect()
        scrollObserver = null
        galleryContainer.replaceChildren()
        renderGalleryChunked(fileData, 20, () => {
            filterGallery()
            if (
                nextPage &&
                document.body.scrollHeight -
                    window.innerHeight -
                    window.scrollY <=
                    0
            ) {
                addNodes() // addNodes calls setupScrollObserver on completion
            } else {
                setupScrollObserver() // content fills viewport; re-arm for future scrolls
            }
        })
    }
    updateNoFilesOverlay()
}

const ALBUM_EVENTS = new Set([
    'set-file-albums',
    'bulk-add-file-albums',
    'bulk-remove-file-albums',
])

function handleFileNew(data, inGallery) {
    fileData.unshift(data)
    if (inGallery) {
        const outer = addGalleryFile(data, true)
        if (outer)
            requestAnimationFrame(() =>
                outer.classList.remove('gallery-entering')
            )
        updateNoFilesOverlay()
    }
}

function animateRemoveGalleryCard(id, callback) {
    const el = document.getElementById(`gallery-image-${id}`)
    if (!el) {
        callback?.()
        return
    }
    el.classList.add('gallery-removing')
    el.addEventListener(
        'transitionend',
        () => {
            el.remove()
            callback?.()
        },
        { once: true }
    )
}

function handleFileDelete(data, inGallery) {
    const idx = fileData.findIndex((file) => file.id === data.id)
    if (idx !== -1) fileData.splice(idx, 1)
    removeFileTableRow(data.id)
    if (inGallery) {
        animateRemoveGalleryCard(data.id, updateNoFilesOverlay)
    }
}

function removeFileFromViews(fileId, inGallery, inMap) {
    const idx = fileData.findIndex((f) => f.id === fileId)
    if (idx !== -1) fileData.splice(idx, 1)
    removeFileTableRow(fileId)
    if (inGallery) {
        animateRemoveGalleryCard(fileId)
    } else if (inMap) {
        const marker = mapFileMarkers.get(fileId)
        if (marker) {
            marker.remove()
            mapFileMarkers.delete(fileId)
        }
    }
}

function addFileToViews(fileId, inGallery, inMap) {
    return fetchFile(fileId).then((file) => {
        fileData.push(file)
        if (inGallery) {
            const outer = addGalleryFile(file, true)
            if (outer)
                requestAnimationFrame(() =>
                    outer.classList.remove('gallery-entering')
                )
            updateNoFilesOverlay()
        } else if (inMap) {
            const L = globalThis.L
            if (L && mapInitialised) {
                addFileMapMarker(L, file)
                if (trackerEnabled) drawTrackerPolyline(L)
            }
            updateNoFilesOverlay()
        } else {
            file['DT_RowId'] = `file-${file.id}`
            addFileTableRowsBatch([file])
        }
    })
}

function handleAlbumChange(data, inGallery, inMap, currentAlbum) {
    if (!currentAlbum) return
    const albumId = Number.parseInt(currentAlbum, 10)
    const affectsAlbum =
        data.event === 'set-file-albums'
            ? (data.removed_from && albumId in data.removed_from) ||
              (data.added_to && albumId in data.added_to)
            : data.albums?.some((a) => a.id === albumId)
    if (!affectsAlbum) return

    const fileIds =
        data.event === 'set-file-albums' ? [data.file_id] : data.pks || []
    const isRemove =
        data.event === 'bulk-remove-file-albums' ||
        (data.event === 'set-file-albums' &&
            data.removed_from &&
            albumId in data.removed_from)
    const isAdd =
        data.event === 'bulk-add-file-albums' ||
        (data.event === 'set-file-albums' &&
            data.added_to &&
            albumId in data.added_to)

    if (isRemove) {
        for (const fileId of fileIds)
            removeFileFromViews(fileId, inGallery, inMap)
        if (inGallery || inMap) updateNoFilesOverlay()
    }
    if (isAdd) {
        Promise.all(
            fileIds.map((fileId) => addFileToViews(fileId, inGallery, inMap))
        )
    }
}

function handleGalleryEvent(data) {
    if (data.event === 'set-password-file') passwordStatusChange(data)
    else if (data.event === 'toggle-private-file') privateStatusChange(data)
    else if (data.event === 'set-file-name') fileRename(data)
    else if (data.event === 'set-expr-file') fileExpireChange(data)
}

socket?.addEventListener('message', function (event) {
    if (event.data === 'pong') return
    const data = JSON.parse(event.data)
    const inGallery = params.get('view') === 'gallery'
    const inMap = params.get('view') === 'map'
    const currentAlbum = params.get('album')

    if (data.event === 'file-new') {
        handleFileNew(data, inGallery)
    } else if (data.event === 'file-delete') {
        handleFileDelete(data, inGallery)
    } else if (ALBUM_EVENTS.has(data.event)) {
        handleAlbumChange(data, inGallery, inMap, currentAlbum)
    } else if (inGallery) {
        handleGalleryEvent(data)
    }
})

function fileExpireChange(data) {
    const expireStatus = document
        .getElementById(`gallery-image-${data.id}`)
        .getElementsByClassName('expireStatus')[0]
    expireStatus.style.visibility = data.expr ? 'visible' : 'hidden'
    expireStatus.title = data.expr
}

function updateNoFilesOverlay() {
    if (!noFilesOverlay) return
    const view = params.get('view') || 'list'
    const isEmpty = fileData.length === 0 && !nextPage
    const show = (view === 'gallery' || view === 'map') && isEmpty

    noFilesOverlay.classList.toggle('d-none', !show)
    noFilesOverlay.classList.toggle('d-flex', show)

    if (show && view === 'map') {
        mapContainer.style.position = 'relative'
        mapContainer.appendChild(noFilesOverlay)
    } else if (noFilesOverlay.parentElement === mapContainer) {
        mapContainer.parentElement.appendChild(noFilesOverlay)
        mapContainer.style.position = ''
    }
}

function passwordStatusChange(data) {
    const passwordStatus = document
        .getElementById(`gallery-image-${data.id}`)
        .getElementsByClassName('passwordStatus')[0]
    passwordStatus.style.visibility = data.password ? 'visible' : 'hidden'
}

function privateStatusChange(data) {
    const privateStatus = document
        .getElementById(`gallery-image-${data.id}`)
        .getElementsByClassName('privateStatus')[0]
    privateStatus.style.visibility = data.private ? 'visible' : 'hidden'
}

function fileRename(data) {
    let fileLabels = document.querySelector(
        `#gallery-image-${data.id} .image-labels`
    )
    fileLabels.innerHTML = ''
    buildImageLabels(data, fileLabels)
    let imageLink = document.querySelector(
        `#gallery-image-${data.id} .image-link`
    )
    imageLink.href = data.uri
}

function buildImageLabels(file, bottomLeft) {
    if (file.size) {
        addSpan(bottomLeft, formatBytes(file.size))
    }
    if (file.meta.PILImageWidth && file.meta.PILImageHeight) {
        const text = `${file.meta.PILImageWidth}x${file.meta.PILImageHeight}`
        addSpan(bottomLeft, text)
    }
    if (file.name) {
        addSpan(bottomLeft, file.name)
    }
}

const mapContainer = document.getElementById('map-container')
let galleryLeafletMap = null
let mapInitialised = false
const mapFileMarkers = new Map()
let trackerFiles = []
let trackerPolyline = null
let trackerStartMarker = null
let trackerEndMarker = null
let trackerArrows = []
let trackerEnabled = params.get('tracker') === '1'

// Promise-valued cache deduplicates concurrent hovers on the same pin
const markerThumbCache = new Map()

// GPS IFD dict has string or int keys; values are DMS arrays
function gpsToDecimal(gpsInfo) {
    if (!gpsInfo || typeof gpsInfo !== 'object') return null
    const latDms = gpsInfo['2'] ?? gpsInfo[2]
    const lonDms = gpsInfo['4'] ?? gpsInfo[4]
    const latRef = (gpsInfo['1'] ?? gpsInfo[1] ?? 'N').toString().toUpperCase()
    const lonRef = (gpsInfo['3'] ?? gpsInfo[3] ?? 'E').toString().toUpperCase()
    if (
        !Array.isArray(latDms) ||
        !Array.isArray(lonDms) ||
        latDms.length < 3 ||
        lonDms.length < 3
    )
        return null
    const lat =
        (latDms[0] + latDms[1] / 60 + latDms[2] / 3600) *
        (latRef === 'S' ? -1 : 1)
    const lon =
        (lonDms[0] + lonDms[1] / 60 + lonDms[2] / 3600) *
        (lonRef === 'W' ? -1 : 1)
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null
    return [lat, lon]
}

function parseExifDatetime(s) {
    if (!s || typeof s !== 'string') return null
    const m = /^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})/.exec(s)
    if (!m) return null
    return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6])
}

function formatMapDatetime(file) {
    const exifDt = parseExifDatetime(file.exif?.DateTimeOriginal)
    const d = exifDt || (file.date ? new Date(file.date) : null)
    if (!d || Number.isNaN(d.getTime())) return ''
    return d.toLocaleString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
    })
}

function fitMapToViewport() {
    if (galleryLeafletMap) galleryLeafletMap.invalidateSize()
}

window.addEventListener('resize', fitMapToViewport)

function initMapView() {
    const L = globalThis.L
    if (!L) return console.error('Leaflet not loaded')

    requestAnimationFrame(() => {
        if (mapInitialised) {
            galleryLeafletMap.invalidateSize()
        } else {
            mapInitialised = true
            galleryLeafletMap = L.map('map-container', {
                zoomControl: true,
            }).setView([20, 0], 2)
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution:
                    '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                maxZoom: 19,
            }).addTo(galleryLeafletMap)

            const FullscreenControl = L.Control.extend({
                options: { position: 'topleft' },
                onAdd() {
                    const container = L.DomUtil.create(
                        'div',
                        'leaflet-bar leaflet-control'
                    )
                    const btn = L.DomUtil.create('a', '', container)
                    btn.href = '#'
                    btn.title = 'Toggle fullscreen'
                    btn.classList.add(
                        'map-fullscreen-btn',
                        'd-flex',
                        'align-items-center',
                        'justify-content-center'
                    )
                    btn.innerHTML = '<i class="fa-solid fa-expand"></i>'
                    L.DomEvent.on(btn, 'click', (e) => {
                        L.DomEvent.preventDefault(e)
                        L.DomEvent.stopPropagation(e)
                        if (document.fullscreenElement) {
                            document.exitFullscreen()
                        } else {
                            mapContainer.requestFullscreen()
                        }
                    })
                    document.addEventListener('fullscreenchange', () => {
                        btn.innerHTML =
                            document.fullscreenElement === mapContainer
                                ? '<i class="fa-solid fa-compress"></i>'
                                : '<i class="fa-solid fa-expand"></i>'
                        galleryLeafletMap.invalidateSize()
                    })
                    return container
                },
            })
            new FullscreenControl().addTo(galleryLeafletMap)

            let arrowRedrawTimer = null
            galleryLeafletMap.on('zoomend', () => {
                if (!trackerEnabled || trackerSorted.length < 2) return
                clearTimeout(arrowRedrawTimer)
                arrowRedrawTimer = setTimeout(
                    () => drawTrackerArrows(L, trackerSorted),
                    150
                )
            })

            fetchAndPlotAllFiles(L)
        }
        // Re-append after Leaflet builds its pane DOM so the overlay
        // sits last in the container and renders above the tile layers.
        updateNoFilesOverlay()
    })
}

// img is src-less on creation; browser makes no request until first tooltip open
function buildMarkerTooltip(file, coords) {
    const [lat, lon] = coords
    const gpsLabel = `${Math.abs(lat).toFixed(4)}° ${lat >= 0 ? 'N' : 'S'}, ${Math.abs(lon).toFixed(4)}° ${lon >= 0 ? 'E' : 'W'}`
    return `
        <div class="map-tooltip">
            <div class="map-tooltip-thumb-wrapper">
                <div class="placeholder-glow position-absolute top-0 start-0 w-100 h-100">
                    <span class="placeholder d-block w-100 h-100"></span>
                </div>
                <img data-file-id="${file.id}"
                     alt="${file.name}"
                     class="map-tooltip-thumb">
            </div>
            <strong class="map-tooltip-name">${file.name}</strong>
            <span class="map-tooltip-date">${formatMapDatetime(file)}</span><br>
            <span class="map-tooltip-gps">${gpsLabel}</span>
        </div>`
}

// Returns a Promise so concurrent hovers on the same pin share one fetch; prefers gallery DOM image → file.thumb
function resolveThumbSrc(file) {
    const id = String(file.id)
    if (markerThumbCache.has(id)) return markerThumbCache.get(id)

    const promise = (async () => {
        const galleryImg = document.querySelector(`#gallery-image-${id} img`)
        const fetchUrl =
            galleryImg?.complete && galleryImg.naturalWidth > 0
                ? galleryImg.currentSrc || galleryImg.src
                : file.thumb
        const response = await fetch(fetchUrl)
        const blob = await response.blob()
        return URL.createObjectURL(blob)
    })()

    markerThumbCache.set(id, promise)
    return promise
}

function makeTrackerPin(L, icon, bg) {
    return L.divIcon({
        html: `<div style="width:30px;height:30px;border-radius:50%;background:${bg};display:flex;align-items:center;justify-content:center;border:2px solid rgba(255,255,255,0.9);box-shadow:0 2px 8px rgba(0,0,0,.45);"><i class="${icon}" style="color:#fff;font-size:13px;"></i></div>`,
        className: '',
        iconSize: [30, 30],
        iconAnchor: [15, 15],
        tooltipAnchor: [0, -18],
    })
}

function segmentBearing(lat1, lon1, lat2, lon2) {
    const toRad = (d) => (d * Math.PI) / 180
    const y = Math.sin(toRad(lon2 - lon1)) * Math.cos(toRad(lat2))
    const x =
        Math.cos(toRad(lat1)) * Math.sin(toRad(lat2)) -
        Math.sin(toRad(lat1)) *
            Math.cos(toRad(lat2)) *
            Math.cos(toRad(lon2 - lon1))
    return (Math.atan2(y, x) * 180) / Math.PI
}

// Desired screen-space gap between consecutive arrows (px)
const ARROW_SPACING_PX = 60

function buildArrowIcon(L, angle) {
    return L.divIcon({
        html: `<svg xmlns="http://www.w3.org/2000/svg" width="10" height="12" viewBox="0 0 10 12"
                    style="transform:rotate(${angle}deg);transform-origin:50% 50%;display:block;overflow:visible;">
                 <path d="M5,0 L10,11 L5,7.5 L0,11 Z"
                       fill="#e85d04" fill-opacity="0.75"
                       stroke="rgba(255,255,255,0.55)" stroke-width="1" stroke-linejoin="round"/>
               </svg>`,
        className: '',
        iconSize: [10, 12],
        iconAnchor: [5, 6],
    })
}

function drawTrackerArrows(L, sorted) {
    trackerArrows.forEach((m) => m.remove())
    trackerArrows = []

    const segments = sorted.length - 1
    if (segments < 1) return

    for (let i = 0; i < segments; i++) {
        const [lat1, lon1] = sorted[i].coords
        const [lat2, lon2] = sorted[i + 1].coords

        const p1 = galleryLeafletMap.latLngToContainerPoint([lat1, lon1])
        const p2 = galleryLeafletMap.latLngToContainerPoint([lat2, lon2])
        const pixelLen = Math.hypot(p2.x - p1.x, p2.y - p1.y)
        const count = Math.floor(pixelLen / ARROW_SPACING_PX)
        if (count < 1) continue

        const angle = segmentBearing(lat1, lon1, lat2, lon2).toFixed(1)
        const icon = buildArrowIcon(L, angle)

        for (let j = 1; j <= count; j++) {
            const t = j / (count + 1)
            trackerArrows.push(
                L.marker([lat1 + (lat2 - lat1) * t, lon1 + (lon2 - lon1) * t], {
                    icon,
                    interactive: false,
                    keyboard: false,
                }).addTo(galleryLeafletMap)
            )
        }
    }
}

let trackerSorted = []

function drawTrackerPolyline(L) {
    if (trackerPolyline) {
        trackerPolyline.remove()
        trackerPolyline = null
    }
    if (trackerStartMarker) {
        trackerStartMarker.remove()
        trackerStartMarker = null
    }
    if (trackerEndMarker) {
        trackerEndMarker.remove()
        trackerEndMarker = null
    }
    trackerArrows.forEach((m) => m.remove())
    trackerArrows = []
    trackerSorted = []

    if (!trackerEnabled || trackerFiles.length < 2) return
    trackerSorted = [...trackerFiles].sort((a, b) => a.dt - b.dt)
    trackerPolyline = L.polyline(
        trackerSorted.map((f) => f.coords),
        { color: '#e85d04', weight: 3, opacity: 0.75, dashArray: '6, 4' }
    ).addTo(galleryLeafletMap)

    drawTrackerArrows(L, trackerSorted)

    trackerStartMarker = L.marker(trackerSorted[0].coords, {
        icon: makeTrackerPin(L, 'fa-solid fa-flag', '#2a9d2a'),
        zIndexOffset: 1000,
    })
        .addTo(galleryLeafletMap)
        .bindTooltip('Start', { direction: 'top' })

    trackerEndMarker = L.marker(trackerSorted.at(-1).coords, {
        icon: makeTrackerPin(L, 'fa-solid fa-flag-checkered', '#dc3545'),
        zIndexOffset: 1000,
    })
        .addTo(galleryLeafletMap)
        .bindTooltip('Finish', { direction: 'top' })
}

function initTrackerBtn() {
    const btn = document.getElementById('map-tracker-btn')
    if (!btn) return
    const syncBtn = () => {
        btn.classList.toggle('view-active', trackerEnabled)
        btn.setAttribute('aria-pressed', trackerEnabled ? 'true' : 'false')
        btn.title = trackerEnabled ? 'Hide tracker path' : 'Show tracker path'
    }
    const syncKmlBtn = () => {
        const kmlBtn = document.getElementById('map-kml-export-btn')
        if (kmlBtn) kmlBtn.classList.toggle('d-none', !trackerEnabled)
    }
    syncBtn()
    syncKmlBtn()
    btn.addEventListener('click', () => {
        trackerEnabled = !trackerEnabled
        const url = new URL(document.location.toString())
        if (trackerEnabled) {
            url.searchParams.set('tracker', '1')
        } else {
            url.searchParams.delete('tracker')
        }
        history.replaceState(null, '', url.toString())
        syncBtn()
        syncKmlBtn()
        const L = globalThis.L
        if (L && mapInitialised) drawTrackerPolyline(L)
    })
}

function escapeXml(str) {
    return str
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
}

function buildKML() {
    const sorted = [...trackerFiles].sort((a, b) => a.dt - b.dt)
    const coordLines = sorted
        .map((f) => `${f.coords[1]},${f.coords[0]},0`)
        .join('\n                ')
    const albumTitle =
        document
            .querySelector('.files-toolbar-album-title')
            ?.textContent.trim() || 'Track'
    return `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>${escapeXml(albumTitle)}</name>
    <Placemark>
      <name>Track</name>
      <LineString>
        <tessellate>1</tessellate>
        <coordinates>
                ${coordLines}
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>`
}

function initKMLExportBtn() {
    const btn = document.getElementById('map-kml-export-btn')
    if (!btn) return
    btn.addEventListener('click', () => {
        if (trackerFiles.length < 2) return
        const blob = new Blob([buildKML()], {
            type: 'application/vnd.google-earth.kml+xml',
        })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `album-${params.get('album') || 'track'}.kml`
        a.click()
        URL.revokeObjectURL(url)
    })
}

function addFileMapMarker(L, file) {
    const coords = gpsToDecimal(file.exif?.GPSInfo)
    if (!coords) return null

    trackerFiles.push({
        coords,
        dt:
            parseExifDatetime(file.exif?.DateTimeOriginal) ||
            new Date(file.date),
    })

    const marker = L.marker(coords)
        .addTo(galleryLeafletMap)
        .bindTooltip(buildMarkerTooltip(file, coords), {
            direction: 'top',
            offset: [-15, -13],
        })
        .on('click', () => {
            openPanel(file.url)
        })
        .on('tooltipopen', async (e) => {
            const el = e.tooltip.getElement()
            if (!el) return
            L.DomEvent.disableClickPropagation(el)
            el.style.cursor = 'pointer'
            L.DomEvent.on(el, 'click', (e) => {
                L.DomEvent.stopPropagation(e)
                openPanel(file.url)
            })
            const img = el.querySelector('img[data-file-id]')
            if (!img) return
            const blobUrl = await resolveThumbSrc(file)
            // Guard: tooltip may have closed before the blob resolved
            if (!img.isConnected) return
            img.src = blobUrl
            img.addEventListener(
                'load',
                () => {
                    img.style.opacity = '1'
                    img.parentElement
                        ?.querySelector('.placeholder-glow')
                        ?.remove()
                },
                { once: true }
            )
        })
    mapFileMarkers.set(file.id, marker)
    return coords
}

async function fetchAndPlotAllFiles(L) {
    let page = 1
    const album = params.get('album')
    const allCoords = []
    trackerFiles = []

    const spinner = document.getElementById('map-loading-spinner')
    const countEl = document.getElementById('total-files-count')
    if (spinner) spinner.classList.remove('d-none')
    if (countEl) countEl.textContent = '0'

    try {
        while (page) {
            const data = await fetchFiles(
                page,
                100,
                album,
                galleryOrdering,
                getActiveTypesParam(),
                { has_gps: 1 }
            )
            page = data.next

            for (const file of data.files) {
                const coords = addFileMapMarker(L, file)
                if (coords) {
                    allCoords.push(coords)
                    if (countEl) countEl.textContent = allCoords.length
                }
            }
        }
    } finally {
        if (spinner) spinner.classList.add('d-none')
    }

    if (allCoords.length === 1) {
        galleryLeafletMap.setView(allCoords[0], 11)
    } else if (allCoords.length > 1) {
        galleryLeafletMap.fitBounds(allCoords, { padding: [40, 40] })
    }

    drawTrackerPolyline(L)
}
