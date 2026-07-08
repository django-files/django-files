// JS for embed/preview.html

import { socket } from './socket.js'
import { initAlbumSelector } from './album-selector.js'
import { initTagSelector } from './tag-selector.js'

document.addEventListener('DOMContentLoaded', domLoaded)
window.addEventListener('resize', checkSize)

const previewSidebar = $('#preview-sidebar')
const openSidebarButton = $('#openSidebar')
openSidebarButton.on('click', openSidebarCallback)
$('#closeSidebar').on('click', closeSidebarCallback)

const sidebarMaxWidth = 768
const noAutoClose = previewSidebar[0]?.dataset.noAutoClose === 'true'
const sidebarCookieKey =
    previewSidebar[0]?.dataset.cookieKey || 'previewSidebar'
let sidebarOpen = false

function getSidebarMode() {
    return localStorage.getItem('sidebarMode') || 'overlay'
}

function getSidebarParent() {
    return previewSidebar[0]?.parentElement
}

function applySidebarMode(mode) {
    const el = previewSidebar[0]
    if (!el) return
    if (mode === 'overlay') {
        getSidebarParent()?.classList.remove('sidebar-push-open')
    }
    updateModeToggleIcon(mode)
    // Re-apply open/closed state for new mode
    if (sidebarOpen) {
        openSidebar()
    } else {
        closeSidebar()
    }
}

function updateModeToggleIcon(mode) {
    const btn = document.querySelector('.sidebar-mode-toggle')
    if (!btn) return
    const icon = btn.querySelector('i')
    if (!icon) return
    if (mode === 'push') {
        icon.className = 'fa-solid fa-layer-group'
        btn.title = 'Switch to overlay mode'
    } else {
        icon.className = 'fa-solid fa-table-columns'
        btn.title = 'Switch to push mode'
    }
}

function toggleSidebarMode() {
    const current = getSidebarMode()
    const next = current === 'overlay' ? 'push' : 'overlay'
    localStorage.setItem('sidebarMode', next)
    applySidebarMode(next)
}

function domLoaded() {
    // Insert mode toggle button into sidebar
    const closebtn = document.getElementById('closeSidebar')
    if (closebtn) {
        const toggleBtn = document.createElement('button')
        toggleBtn.className = 'sidebar-mode-toggle'
        toggleBtn.innerHTML = '<i class="fa-solid fa-table-columns"></i>'
        toggleBtn.addEventListener('click', toggleSidebarMode)
        closebtn.parentElement.insertBefore(toggleBtn, closebtn)
    }

    applySidebarMode(getSidebarMode())

    if (window.innerWidth >= sidebarMaxWidth) {
        if (!Cookies.get(sidebarCookieKey)) {
            requestAnimationFrame(() =>
                requestAnimationFrame(() => openSidebar())
            )
        }
    }
    initPreviewImage()
    initMarkdownToggle()
}

const MD_SESSION_KEY = 'mdView'

async function loadMarkdownSource(rendered, source, codeEl, rawUrl) {
    rendered.classList.add('d-none')
    source.classList.remove('d-none')

    if (codeEl.dataset.loaded) return
    codeEl.dataset.loaded = '1'

    try {
        const response = await fetch(rawUrl)
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const text = await response.text()
        codeEl.textContent = text

        const theme = document.documentElement.dataset.bsTheme
        if (theme !== 'dark') {
            document.getElementById('code-dark')?.setAttribute('disabled', '')
            document.getElementById('code-light')?.removeAttribute('disabled')
        }

        globalThis.hljs?.highlightElement(codeEl)
    } catch (e) {
        codeEl.textContent = `Error loading file: ${e.message}`
    }
}

async function initMarkdownToggle() {
    const card = document.querySelector('.card[data-render="markdown"]')
    if (!card) return

    const btnRendered = document.getElementById('mdViewRendered')
    const btnSource = document.getElementById('mdViewSource')
    const rendered = document.getElementById('md-rendered')
    const source = document.getElementById('md-source')
    const codeEl = document.getElementById('text-preview')

    if (!btnRendered || !btnSource || !rendered || !source || !codeEl) return

    const rawUrl = card.dataset.rawUrl

    function setActive(showSource) {
        btnRendered.classList.toggle('active', !showSource)
        btnSource.classList.toggle('active', showSource)
    }

    // ?md_view=source|rendered overrides; anything else falls back to session > default (rendered)
    const qp = new URLSearchParams(location.search).get('md_view')
    let startSource
    if (qp === 'source') {
        startSource = true
    } else if (qp === 'rendered') {
        startSource = false
    } else {
        startSource = sessionStorage.getItem(MD_SESSION_KEY) === 'source'
    }

    if (startSource) {
        setActive(true)
        await loadMarkdownSource(rendered, source, codeEl, rawUrl)
    }

    btnSource.addEventListener('click', async () => {
        sessionStorage.setItem(MD_SESSION_KEY, 'source')
        setActive(true)
        await loadMarkdownSource(rendered, source, codeEl, rawUrl)
    })

    btnRendered.addEventListener('click', () => {
        sessionStorage.setItem(MD_SESSION_KEY, 'rendered')
        setActive(false)
        source.classList.add('d-none')
        rendered.classList.remove('d-none')
    })
}

function initPreviewImage() {
    const img = document.querySelector('img.preview')
    if (!img) return
    const skeleton = document.getElementById('img-skeleton')

    if (skeleton?.dataset.thumb) {
        const thumb = new Image()
        thumb.onload = () => {
            skeleton.style.backgroundImage = `url(${thumb.src})`
            skeleton.classList.add('has-thumb')
        }
        thumb.src = skeleton.dataset.thumb
    }

    const onLoad = () => {
        img.style.opacity = '1'
        if (skeleton) {
            skeleton.style.transition = 'opacity 0.4s ease-out'
            skeleton.style.opacity = '0'
            skeleton.addEventListener(
                'transitionend',
                () => skeleton.remove(),
                { once: true }
            )
        }
    }

    const onError = () => {
        if (skeleton) skeleton.remove()
        img.style.display = 'none'
        const wrapper = img.closest('.preview-wrapper')
        if (wrapper) {
            const placeholder = document.createElement('div')
            placeholder.className = 'img-error-placeholder'
            placeholder.innerHTML = `
                <i class="fa-solid fa-file-image"></i>
                <p>This image format is not supported by your browser.</p>
            `
            wrapper.appendChild(placeholder)
        }
    }

    if (img.complete) {
        // Already settled before listeners attached (e.g. cached)
        if (img.naturalWidth === 0) {
            onError()
        } else {
            onLoad()
        }
    } else {
        img.addEventListener('load', onLoad, { once: true })
        img.addEventListener('error', onError, { once: true })
    }
}

function checkSize() {
    if (window.innerWidth >= sidebarMaxWidth) {
        if (!sidebarOpen) {
            if (!Cookies.get(sidebarCookieKey)) {
                openSidebar()
            }
        }
    } else if (sidebarOpen && !noAutoClose) {
        closeSidebar()
    }
}

function openSidebarCallback() {
    openSidebar()
    Cookies.remove(sidebarCookieKey)
}

function closeSidebarCallback() {
    closeSidebar()
    Cookies.set(sidebarCookieKey, 'disabled', { expires: 365 })
}

function openSidebar() {
    sidebarOpen = true
    previewSidebar.addClass('open')
    getSidebarParent()?.classList.add('sidebar-open')
    if (getSidebarMode() === 'push') {
        getSidebarParent()?.classList.add('sidebar-push-open')
    }
    openSidebarButton.hide()
}

function closeSidebar() {
    sidebarOpen = false
    previewSidebar.removeClass('open')
    getSidebarParent()?.classList.remove('sidebar-open')
    getSidebarParent()?.classList.remove('sidebar-push-open')
    openSidebarButton.show()
}

window.openSidebar = openSidebar
window.closeSidebar = closeSidebar
window.tryOpenSidebar = () => {
    if (!Cookies.get(sidebarCookieKey)) openSidebar()
}

function renameFile(data) {
    let fileName = document.getElementsByClassName('card-title')[0]
    fileName.innerHTML = data.name
    window.history.pushState({}, '', data.uri)
}

socket?.addEventListener('message', function (event) {
    if (event.data === 'pong') return
    let data = JSON.parse(event.data)
    if (data.event === 'set-file-name') {
        renameFile(data)
    } else if (data.event === 'set-file-albums') {
        handleAlbumBadges(data)
    } else if (data.event === 'set-file-tags') {
        handleTagUpdate(data)
    } else if (data.event === 'set-stream-title') {
        handleStreamTitleUpdate(data)
    } else if (data.event === 'set-stream-description') {
        handleStreamDescriptionUpdate(data)
    }
})

function handleStreamTitleUpdate(data) {
    const titleEl = document.querySelector('.stream-title')
    if (titleEl) {
        titleEl.textContent = data.title
    }
}

function handleStreamDescriptionUpdate(data) {
    const descEl = document.querySelector('.stream-desc')
    if (descEl) {
        descEl.textContent = data.description
    }
}

// Stream title editing
const streamTitleEdit = document.querySelector('.stream-title.stream-editable')
if (streamTitleEdit) {
    let originalTitle = streamTitleEdit.textContent.trim()

    streamTitleEdit.addEventListener('focus', function () {
        originalTitle = this.textContent.trim()
    })

    streamTitleEdit.addEventListener('blur', function () {
        const newTitle = this.textContent.trim()
        if (newTitle && newTitle !== originalTitle) {
            originalTitle = newTitle
            socket.send(
                JSON.stringify({
                    method: 'set-stream-title',
                    name: this.dataset.streamName,
                    title: newTitle,
                })
            )
        }
    })

    streamTitleEdit.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault()
            this.blur()
        } else if (e.key === 'Escape') {
            this.textContent = originalTitle
            this.blur()
        }
    })
}

// Stream description editing
const streamDescEdit = document.querySelector('.stream-desc.stream-editable')
if (streamDescEdit) {
    let originalDesc = streamDescEdit.textContent.trim()

    streamDescEdit.addEventListener('focus', function () {
        originalDesc = this.textContent.trim()
    })

    streamDescEdit.addEventListener('blur', function () {
        const newDesc = this.textContent.trim()
        if (newDesc !== originalDesc) {
            originalDesc = newDesc
            socket.send(
                JSON.stringify({
                    method: 'set-stream-description',
                    name: this.dataset.streamName,
                    description: newDesc,
                })
            )
        }
    })

    streamDescEdit.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault()
            this.blur()
        } else if (e.key === 'Escape') {
            this.textContent = originalDesc
            this.blur()
        }
    })
}

////////////////////////
// Album Badges Section
const handleAlbumBadges = initAlbumSelector(document, socket)
// End Album Badges Section
////////////////////////////

////////////////////////////
// Tag Badges Section
const handleTagUpdate = initTagSelector(document, socket)
// End Tag Badges Section
////////////////////////////

////////////////////////////
// Leaflet Map Section
const mapToggle = document.getElementById('mapToggle')
const mapCollapse = document.getElementById('mapCollapse')
const mapContainer = document.getElementById('preview-map')
let leafletMap = null

function openMap() {
    mapCollapse.style.display = 'block'
    mapToggle.setAttribute('aria-expanded', 'true')
    mapToggle.querySelector('span').textContent = 'Hide Map'
    Cookies.set('previewMap', 'open', { expires: 365 })
    requestAnimationFrame(() => {
        if (leafletMap) {
            leafletMap.invalidateSize()
        } else {
            initLeafletMap()
        }
    })
}

function closeMap() {
    mapCollapse.style.display = 'none'
    mapToggle.setAttribute('aria-expanded', 'false')
    mapToggle.querySelector('span').textContent = 'Show on Map'
    Cookies.remove('previewMap')
}

if (mapToggle && mapCollapse && mapContainer) {
    mapToggle.addEventListener('click', () => {
        if (mapToggle.getAttribute('aria-expanded') === 'true') {
            closeMap()
        } else {
            openMap()
        }
    })

    if (Cookies.get('previewMap') === 'open') {
        openMap()
    }
}

function initLeafletMap() {
    const L = globalThis.L
    if (!L) {
        console.error('Leaflet not loaded')
        return
    }
    const lat = Number.parseFloat(mapContainer.dataset.lat)
    const lon = Number.parseFloat(mapContainer.dataset.lon)
    leafletMap = L.map('preview-map', {
        zoomControl: false,
        attributionControl: true,
    }).setView([lat, lon], 7)

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution:
            '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
    }).addTo(leafletMap)

    L.marker([lat, lon]).addTo(leafletMap)
    // Second invalidateSize in case one frame wasn't enough
    requestAnimationFrame(() => leafletMap.invalidateSize())
}
// End Leaflet Map Section
////////////////////////////
