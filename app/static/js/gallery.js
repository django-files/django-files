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

const galleryContainer = document.getElementById('gallery-container')

const imageNode = document.querySelector('div.d-none > img')

let showGallery = document.querySelector('.show-gallery')
showGallery.onclick = changeView
let showList = document.querySelector('.show-list')
showList.onclick = changeView
let showMap = document.querySelector('.show-map')
showMap.onclick = changeView

let params = new URL(document.location.toString()).searchParams

let dtContainer
let narrowViewportMsg
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

document.addEventListener('DOMContentLoaded', initGallery)

async function initGallery() {
    history.scrollRestoration = 'manual'
    filesDataTable = initFilesTable()
    dtContainer = document.querySelector('.dt-container')
    narrowViewportMsg = document.querySelector('.files-table-narrow-msg')
    if (params.get('view') === 'map') {
        dtContainer.hidden = true
        if (narrowViewportMsg) narrowViewportMsg.hidden = true
        galleryContainer.classList.add('d-none')
        showMap.style.fontWeight = 'bold'
        await addNodes()
        initMapView()
    } else if (globalThis.location.pathname.includes('gallery')) {
        dtContainer.hidden = true
        if (narrowViewportMsg) narrowViewportMsg.hidden = true
        galleryContainer.classList.remove('d-none')
        showGallery.style.fontWeight = 'bold'
        if (mapFileCount) mapFileCount.classList.remove('d-none')
        await addNodes()
    } else {
        galleryContainer.classList.add('d-none')
        showList.style.fontWeight = 'bold'
        await addNodes()
    }
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

$('#user').on('change', function (_event) {
    let user = $(this).val()
    if (user) {
        let url = new URL(location.href)
        url.searchParams.set('user', user)
        location.href = url.href
    }
})

function showSkeletons() {
    if (!nextPage) return

    if (!globalThis.location.pathname.includes('gallery')) {
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
    console.debug('addNodes data:', data)
    slideshowCallback(data)
    nextPage = data.next
    fileData.push(...data.files)
    if (globalThis.location.pathname.includes('gallery') && mapFileCountValue) {
        mapFileCountValue.textContent = fileData.length
    }
    hideSkeletons()
    if (window.location.pathname.includes('gallery')) {
        data.files.forEach((file) => addGalleryFile(file))
    } else if (!window.location.pathname.includes('files')) {
        console.error('Unknown View')
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

function fadeOutSkeleton(skeleton) {
    skeleton.style.transition = 'opacity 0.3s'
    skeleton.style.opacity = '0'
    skeleton.addEventListener('transitionend', () => skeleton.remove(), {
        once: true,
    })
}

function revealVideoThumb(objectUrl, img, skeleton) {
    img.onload = () => {
        URL.revokeObjectURL(objectUrl)
        img.style.visibility = ''
        fadeOutSkeleton(skeleton)
    }
    img.src = objectUrl
}

function showVideoThumbError(skeleton, inner) {
    skeleton.remove()
    const placeholder = document.createElement('div')
    placeholder.className = 'img-error-placeholder'
    placeholder.innerHTML = '<i class="fa-solid fa-file-video"></i>'
    inner.appendChild(placeholder)
}

/**
 * Poll a thumbnail URL until the server returns an image Content-Type,
 * meaning the Celery thumb task has finished. Then set the visible img src
 * and fade the skeleton out. Falls back to a static icon after exhausting
 * retries.
 */
function pollVideoThumb(src, img, skeleton, inner, retries = 10, delay = 1000) {
    const maxDelay = 30000
    const retry = () => {
        if (retries > 0) {
            pollVideoThumb(
                src,
                img,
                skeleton,
                inner,
                retries - 1,
                Math.min(delay * 2, maxDelay)
            )
        } else {
            showVideoThumbError(skeleton, inner)
        }
    }
    // Use the fetched body as the image source via createObjectURL so the
    // thumb is rendered from the single fetch — no second network request
    // when img.src is set, and no dependence on HTTP cache behavior, Vary
    // headers, or DevTools "Disable cache".
    const handleResponse = (res) => {
        if (!res.ok || !res.headers.get('Content-Type')?.startsWith('image/')) {
            retry()
            return null
        }
        return res.blob().then((blob) => {
            revealVideoThumb(URL.createObjectURL(blob), img, skeleton)
        })
    }
    setTimeout(() => {
        fetch(src, { method: 'GET', credentials: 'omit' })
            .then(handleResponse)
            .catch(retry)
    }, delay)
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
    event.currentTarget._mouseEls?.forEach((el) => el.classList.add('d-none'))
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
    const view =
        event.currentTarget.dataset.view ||
        event.currentTarget.textContent.trim()

    // Reset all nav weights
    showList.style.fontWeight = 'normal'
    showGallery.style.fontWeight = 'normal'
    showMap.style.fontWeight = 'normal'

    // Hide all view containers
    galleryContainer.classList.add('d-none')
    mapContainer.classList.add('d-none')
    mapContainer.parentElement.classList.remove('map-view-active')
    if (mapFileCount) mapFileCount.classList.add('d-none')
    dtContainer.hidden = true
    if (narrowViewportMsg) narrowViewportMsg.hidden = true

    if (view === 'List') {
        params.delete('view')
        galleryContainer.replaceChildren()
        dtContainer.hidden = false
        if (narrowViewportMsg) narrowViewportMsg.hidden = false
        globalThis.history.replaceState({}, null, '/files/?' + params)
        showList.style.fontWeight = 'bold'
        filesDataTable.responsive.recalc()
    } else if (view === 'Map') {
        params.set('view', 'map')
        globalThis.history.replaceState({}, null, '/files/?' + params)
        showMap.style.fontWeight = 'bold'
        initMapView()
    } else {
        // Gallery
        params.delete('view')
        selectedFileIds = []
        filesDataTable.rows('.selected').every(function () {
            selectedFileIds.push(this.data().id)
        })
        galleryContainer.classList.remove('d-none')
        globalThis.history.replaceState({}, null, '/gallery/?' + params)
        galleryContainer.replaceChildren()
        showGallery.style.fontWeight = 'bold'
        if (mapFileCount) mapFileCount.classList.remove('d-none')
        if (mapFileCountValue) mapFileCountValue.textContent = fileData.length
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
    if (window.location.pathname.includes('gallery')) {
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
const mapFileCount = document.getElementById('map-file-count')
const mapFileCountValue = document.getElementById('map-file-count-value')
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

    mapContainer.classList.remove('d-none')
    mapContainer.parentElement.classList.add('map-view-active')
    if (mapFileCount) mapFileCount.classList.remove('d-none')
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
            <span class="map-tooltip-gps">${gpsLabel}</span><br>
            <a href="${file.url}" class="map-tooltip-link">View file →</a>
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
    let totalLoaded = 0

    while (page) {
        const data = await fetchFiles(page, 100, album)
        page = data.next
        totalLoaded += data.files.length
        if (mapFileCountValue) mapFileCountValue.textContent = totalLoaded

        for (const file of data.files) {
            const coords = gpsToDecimal(file.exif?.GPSInfo)
            if (!coords) continue

            allCoords.push(coords)

            L.marker(coords)
                .addTo(galleryLeafletMap)
                .bindTooltip(buildMarkerTooltip(file, coords), {
                    direction: 'top',
                    offset: [0, -8],
                })
                .on('click', () => {
                    globalThis.location.href = file.url
                })
                .on('tooltipopen', async (e) => {
                    const img = e.tooltip
                        .getElement()
                        ?.querySelector('img[data-file-id]')
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
