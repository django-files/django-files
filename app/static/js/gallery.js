// Gallery JS
import {
    initFilesTable,
    faLock,
    faKey,
    faHourglass,
    addFileTableRowsBatch,
    formatBytes,
    faCaret,
    showTableSkeletons,
    hideTableSkeletons,
} from './file-table.js'

import { fetchFiles } from './api-fetch.js'

import { socket } from './socket.js'
import { getCtxMenuContainer } from './file-context-menu.js'
import { openPanel } from './file-preview-panel.js'

const galleryContainer = document.getElementById('gallery-container')

const imageNode = document.querySelector('div.d-none > img')

let showGallery = document.querySelector('.show-gallery')
if (showGallery) showGallery.onclick = changeView
let showList = document.querySelector('.show-list')
if (showList) showList.onclick = changeView
let showMap = document.querySelector('.show-map')
if (showMap) showMap.onclick = changeView

let params = new URL(document.location.toString()).searchParams

let nextPage = 1
let fileData = []
let fetchLock = false
let filesDataTable
let selectedFileIds = []
let scrollObserver = null

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
const tmplCtxToggle = document.querySelector('.d-none .gallery-ctx-toggle')
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
        openPanel(galleryLink.href)
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
}

function detectInitialView() {
    const v = params.get('view')
    if (v === 'map') return 'map'
    if (v === 'gallery') return 'gallery'
    return 'list'
}

function wireToolbarSearch() {
    const input = document.getElementById('files-toolbar-search-input')
    if (!input || !filesDataTable) return
    let timer
    input.addEventListener('input', () => {
        clearTimeout(timer)
        timer = setTimeout(() => {
            filesDataTable.search(input.value).draw()
        }, 200)
    })
}

// Keep --navbar-h in sync with the real navbar height so the files-toolbar
// sits flush below it with no gap (hardcoded 52px in CSS is just a fallback).
function syncNavbarHeight() {
    const navbar = document.querySelector('.navbar')
    if (!navbar) return
    const sync = () =>
        document.documentElement.style.setProperty(
            '--navbar-h',
            `${navbar.offsetHeight}px`
        )
    sync()
    new ResizeObserver(sync).observe(navbar)
}

// Keep --files-toolbar-h in sync with the rendered toolbar height so
// list/gallery padding tracks wraps to two rows on narrow viewports.
function observeToolbarHeight() {
    const toolbar = document.getElementById('files-toolbar')
    const container = toolbar?.parentElement
    if (!toolbar || !container) return
    const sync = () =>
        container.style.setProperty(
            '--files-toolbar-h',
            `${toolbar.offsetHeight}px`
        )
    sync()
    new ResizeObserver(sync).observe(toolbar)
}

async function initGallery() {
    history.scrollRestoration = 'manual'
    filesDataTable = initFilesTable()
    wireToolbarSearch()
    syncNavbarHeight()
    observeToolbarHeight()

    const view = detectInitialView()
    applyView(view)
    await addNodes()
    if (view === 'map') initMapView()

    setupScrollObserver()
    filesDataTable.on('select', function (_e, dt, _type, _indexes) {
        document.getElementById('bulk-actions').disabled = false
        let checkbox = document.getElementById(`file-${dt.data().id}`)
        if (checkbox) {
            checkbox.classList.remove('d-none')
        }
    })
    filesDataTable.on('deselect', function (_e, _dt, _type, _indexes) {
        if (filesDataTable.rows({ selected: true }).count() === 0) {
            document.getElementById('bulk-actions').disabled = true
        }
    })
    filesDataTable?.columns.adjust().draw()
}

$('#user').on('change', async function (_event) {
    const userId = $(this).val()
    if (userId) {
        params.set('user', userId)
    } else {
        params.delete('user')
    }
    const newPath = '/files/?' + params
    globalThis.history.replaceState({}, null, newPath)

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
        }
        document.getElementById('map-container').innerHTML = ''
        initMapView()
    } else {
        await addNodes()
    }
})

function showSkeletons() {
    if (!nextPage) return

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
        inner.style.minWidth = '256px'
        inner.style.minHeight = '256px'
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

    const data = await fetchFiles(nextPage, 50, params.get('album'))
    slideshowCallback(data)
    nextPage = data.next
    fileData.push(...data.files)
    hideSkeletons()
    if (params.get('view') === 'gallery') {
        data.files.forEach((file) => addGalleryFile(file))
    }
    addFileTableRowsBatch(data.files)
    fetchLock = false

    if (atBottom && nextPage) {
        window.scrollTo({
            top: document.body.scrollHeight - window.innerHeight,
            behavior: 'instant',
        })
    }
    if (nextPage) setupScrollObserver()
}

function addGalleryFile(file, top = false) {
    if (file.mime?.startsWith('video/')) {
        addGalleryVideo(file, top)
    } else {
        addGalleryImage(file, top)
    }
}

function buildGalleryCard(file, top = false) {
    const outer = tmplOuter.cloneNode(false)
    outer.id = `gallery-image-${file.id}`
    outer.addEventListener('mouseover', mouseOver)
    outer.addEventListener('mouseout', mouseOut)

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
    toggle.appendChild(faCaret.cloneNode(true))
    ctxMenu.appendChild(toggle)
    outer.appendChild(ctxMenu)
    const menu = getCtxMenuContainer(file)
    menu.style.zIndex = '1'
    ctxMenu.appendChild(menu)

    inner.appendChild(buildGalleryCheckbox(file))

    // Cache .gallery-mouse elements to avoid querySelectorAll on every hover
    outer._mouseEls = [...outer.querySelectorAll('.gallery-mouse')]

    if (top) {
        galleryContainer.insertBefore(outer, galleryContainer.firstChild)
    } else {
        galleryContainer.appendChild(outer)
    }

    return { outer, inner }
}

function addGalleryImage(file, top = false) {
    const imageExtensions = /\.(gif|ico|jpeg|jpg|png|webp|jxl|avif)$/i
    if (!file.name.match(imageExtensions)) {
        console.debug(`Skipping non-image: ${file.name}`)
        return
    }

    const maxThumbSize = 256
    const { inner } = buildGalleryCard(file, top)

    // IMAGE AND LINK
    const link = document.createElement('a')
    link.classList.add('image-link')
    link.href = file.url
    link.title = file.name
    link.target = '_blank'
    const img = imageNode.cloneNode(true)

    if (file.meta?.PILImageWidth && file.meta?.PILImageHeight) {
        const scale = Math.min(
            maxThumbSize / file.meta.PILImageWidth,
            maxThumbSize / file.meta.PILImageHeight
        )
        img.width = Math.round(file.meta.PILImageWidth * scale)
        img.height = Math.round(file.meta.PILImageHeight * scale)
    } else {
        img.width = maxThumbSize
        img.height = maxThumbSize
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
            inner.style.minWidth = `${img.width || maxThumbSize}px`
            inner.style.minHeight = `${img.height || maxThumbSize}px`
            const placeholder = document.createElement('div')
            placeholder.className = 'img-error-placeholder'
            placeholder.innerHTML = '<i class="fa-solid fa-file-image"></i>'
            inner.appendChild(placeholder)
        },
        { once: true }
    )

    img.src = file.thumb || file.raw
    link.appendChild(img)
    inner.prepend(skeleton, link)
}

/**
 * Poll a thumbnail URL with HEAD requests (headers only — no body download)
 * until the server returns an image Content-Type, meaning the Celery thumb
 * task has finished. Then set the visible img src and fade the skeleton out.
 * Falls back to a static icon after exhausting retries.
 */
function pollVideoThumb(src, img, skeleton, inner, retries = 10, delay = 3000) {
    fetch(src, { method: 'HEAD' })
        .then((res) => {
            if (
                res.ok &&
                res.headers.get('Content-Type')?.startsWith('image/')
            ) {
                img.onload = () => {
                    img.style.visibility = ''
                    skeleton.style.transition = 'opacity 0.3s'
                    skeleton.style.opacity = '0'
                    skeleton.addEventListener(
                        'transitionend',
                        () => skeleton.remove(),
                        { once: true }
                    )
                }
                img.src = src
            } else if (retries > 0) {
                setTimeout(
                    () =>
                        pollVideoThumb(
                            src,
                            img,
                            skeleton,
                            inner,
                            retries - 1,
                            delay
                        ),
                    delay
                )
            } else {
                skeleton.remove()
                const placeholder = document.createElement('div')
                placeholder.className = 'img-error-placeholder'
                placeholder.innerHTML = '<i class="fa-solid fa-file-video"></i>'
                inner.appendChild(placeholder)
            }
        })
        .catch(() => {
            if (retries > 0) {
                setTimeout(
                    () =>
                        pollVideoThumb(
                            src,
                            img,
                            skeleton,
                            inner,
                            retries - 1,
                            delay
                        ),
                    delay
                )
            }
        })
}

function addGalleryVideo(file, top = false) {
    const maxThumbSize = 256
    const { inner } = buildGalleryCard(file, top)

    const link = document.createElement('a')
    link.classList.add('image-link')
    link.href = file.url
    link.title = file.name
    link.target = '_blank'

    const playBtn = document.createElement('div')
    playBtn.classList.add('video-play-overlay')
    playBtn.innerHTML =
        '<i class="fa-solid fa-circle-play fa-3x text-white"></i>'

    // hidden img is the in-flow spacer giving gallery-inner its height; skeleton shimmer sits above it
    const img = imageNode.cloneNode(true)
    img.width = maxThumbSize
    img.height = maxThumbSize
    img.style.visibility = 'hidden'

    const skeleton = document.createElement('div')
    skeleton.classList.add('img-skeleton')

    link.appendChild(img)
    // prepend order: link(in-flow) at base, skeleton(abs) covers it, playBtn(abs) on top
    inner.prepend(playBtn, skeleton, link)

    if (file.thumb) {
        // Thumb URL may still serve the raw video while the Celery task runs.
        // HEAD-poll (no body downloaded) until Content-Type is an image.
        pollVideoThumb(file.thumb, img, skeleton, inner)
    }
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
    event.currentTarget._mouseEls?.forEach((el) =>
        el.classList.remove('d-none')
    )
}

function mouseOut(event) {
    // TODO: Fix mouse out detection when mousing over ctx menu
    if (event.target.closest('a')?.classList.contains('ctx-menu')) return
    event.currentTarget._mouseEls?.forEach((el) => {
        if (el.classList.contains('gallery-checkbox') && el.checked) return
        el.classList.add('d-none')
    })
}

// Yields to the browser between batches so painting is incremental rather than a single blocking call
function renderGalleryChunked(files, chunkSize = 20, onComplete = null) {
    let i = 0
    function renderNext() {
        const end = Math.min(i + chunkSize, files.length)
        while (i < end) {
            addGalleryFile(files[i++])
        }
        if (i < files.length) {
            requestAnimationFrame(renderNext)
        } else if (onComplete) {
            onComplete()
        }
    }
    requestAnimationFrame(renderNext)
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

    if (view === 'list') {
        galleryContainer.replaceChildren()
        filesDataTable.responsive.recalc()
    } else if (view === 'map') {
        initMapView()
    } else {
        galleryContainer.replaceChildren()
        renderGalleryChunked(fileData, 20, () => {
            if (
                nextPage &&
                document.body.scrollHeight -
                    window.innerHeight -
                    window.scrollY <=
                    0
            ) {
                addNodes()
            }
        })
    }
}

socket?.addEventListener('message', function (event) {
    if (event.data === 'pong') return
    if (params.get('view') === 'gallery') {
        let data = JSON.parse(event.data)
        if (data.event === 'file-delete') {
            fileDeleteGallery(data.id)
        } else if (data.event === 'file-new') {
            addGalleryFile(data, true)
        } else if (data.event === 'set-password-file') {
            passwordStatusChange(data)
        } else if (data.event === 'toggle-private-file') {
            privateStatusChange(data)
        } else if (data.event === 'set-file-name') {
            fileRename(data)
        } else if (data.event === 'set-expr-file') {
            fileExpireChange(data)
        }
    }
})

function fileExpireChange(data) {
    const expireStatus = document
        .getElementById(`gallery-image-${data.id}`)
        .getElementsByClassName('expireStatus')[0]
    expireStatus.style.visibility = data.expr ? 'visible' : 'hidden'
    expireStatus.title = data.expr
}

function fileDeleteGallery(pk) {
    $(`#gallery-image-${pk}`).remove()
    const idx = fileData.findIndex((file) => file.id === pk)
    if (idx !== -1) fileData.splice(idx, 1)
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

function formatMapDate(dateVal) {
    if (!dateVal) return ''
    const d = new Date(dateVal)
    if (Number.isNaN(d)) return String(dateVal)
    return d.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
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
                    btn.classList.add('map-fullscreen-btn')
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

            fetchAndPlotAllFiles(L)
        }
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
            <span class="map-tooltip-date">${formatMapDate(file.date)}</span><br>
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

async function fetchAndPlotAllFiles(L) {
    let page = 1
    const album = params.get('album')
    const allCoords = []

    while (page) {
        const data = await fetchFiles(page, 100, album)
        page = data.next

        for (const file of data.files) {
            const coords = gpsToDecimal(file.exif?.GPSInfo)
            if (!coords) continue

            allCoords.push(coords)

            L.marker(coords)
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
        }
    }

    if (allCoords.length === 1) {
        galleryLeafletMap.setView(allCoords[0], 11)
    } else if (allCoords.length > 1) {
        galleryLeafletMap.fitBounds(allCoords, { padding: [40, 40] })
    }
}
