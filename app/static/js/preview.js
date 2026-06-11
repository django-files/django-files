// JS for embed/preview.html

import { socket } from './socket.js'
import { fetchFile, fetchAlbumsSearch } from './api-fetch.js'

document.addEventListener('DOMContentLoaded', domLoaded)
window.addEventListener('resize', checkSize)

const previewSidebar = $('#preview-sidebar')
const openSidebarButton = $('#openSidebar')
openSidebarButton.on('click', openSidebarCallback)
$('#closeSidebar').on('click', closeSidebarCallback)

const sidebarMaxWidth = 768
const noAutoClose = previewSidebar[0]?.dataset.noAutoClose === 'true'
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
        if (!Cookies.get('previewSidebar')) {
            openSidebar()
        }
    }
    initPreviewImage()
}

function initPreviewImage() {
    const img = document.querySelector('img.preview')
    if (!img) return
    const skeleton = document.getElementById('img-skeleton')

    const onLoad = () => {
        img.style.opacity = '1'
        if (skeleton) {
            skeleton.style.transition = 'opacity 0.3s'
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
            if (!Cookies.get('previewSidebar')) {
                openSidebar()
            }
        }
    } else if (sidebarOpen && !noAutoClose) {
        closeSidebar()
    }
}

function openSidebarCallback() {
    openSidebar()
    Cookies.remove('previewSidebar')
}

function closeSidebarCallback() {
    closeSidebar()
    Cookies.set('previewSidebar', 'disabled', { expires: 365 })
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
const addToAlbumButton = document.querySelector('.addto-album')
const addAlbumInput = document.getElementById('add-album')
const addAlbumContainer = document.querySelector('.album-add-container')
const albumSearchResults = document.getElementById('album-search-results')

let filePk
const albumContainer = document.querySelector('.album-container')

if (albumContainer) {
    filePk = albumContainer.id.replace('albums-file-', '')
}

function handleAlbumBadges(data) {
    const container = document.querySelector('.album-container')
    if (data.removed_from) {
        for (const [key] of Object.entries(data.removed_from)) {
            document.getElementById(`album-${key}`)?.remove()
        }
    }
    if (data.added_to) {
        const addGroup = document.querySelector('.addto-album-group')
        for (const [key, value] of Object.entries(data.added_to)) {
            const span = document.createElement('span')
            span.className =
                'badge rounded-pill text-bg-primary ps-2 ms-1 file-album-active pb-0 pt-0 mt-1 mb-1'
            span.id = `album-${key}`
            span.innerHTML = `
                <a class="text-reset text-decoration-none p-0" href="/files/?view=gallery&album=${key}">${value} </a>
                <button id="remove-album-${key}" class="btn p-0 mt-0 remove-album">
                    <i class="fa-solid fa-xmark text-small remove-album"></i>
                </button>`
            span.querySelector('.remove-album').addEventListener(
                'click',
                removeAlbumPress
            )
            addGroup.before(span)
        }
    }
}

document
    .querySelectorAll('.remove-album')
    .forEach((el) => el.addEventListener('click', removeAlbumPress))

function removeAlbumPress(event) {
    const albumId = event.target
        .closest('button')
        .id.replace('remove-album-', '')
    socket.send(
        JSON.stringify({
            album: albumId,
            pk: filePk,
            method: 'remove_file_album',
        })
    )
}

// Album search dropdown
let albumSearchTimer

function renderAlbumDropdown(albums, query) {
    albumSearchResults.innerHTML = ''
    for (const album of albums) {
        const li = document.createElement('li')
        const a = document.createElement('a')
        a.className = 'dropdown-item'
        a.href = '#'
        a.textContent = album.name
        a.addEventListener('mousedown', (e) => {
            e.preventDefault()
            selectAlbum(album.name)
        })
        li.appendChild(a)
        albumSearchResults.appendChild(li)
    }
    if (query) {
        const li = document.createElement('li')
        if (albums.length) {
            li.innerHTML = '<li><hr class="dropdown-divider"></li>'
            albumSearchResults.appendChild(li.firstChild)
        }
        const createLi = document.createElement('li')
        const a = document.createElement('a')
        a.className = 'dropdown-item'
        a.href = '#'
        a.innerHTML = `<i class="fa-solid fa-plus me-1"></i> Create <strong>${query}</strong>`
        a.addEventListener('mousedown', (e) => {
            e.preventDefault()
            selectAlbum(query)
        })
        createLi.appendChild(a)
        albumSearchResults.appendChild(createLi)
    }
    albumSearchResults.classList.toggle('show', albums.length > 0 || !!query)
}

function selectAlbum(name) {
    socket.send(
        JSON.stringify({
            album_name: name,
            pk: filePk,
            method: 'add_file_album',
        })
    )
    addAlbumInput.value = ''
    addAlbumContainer.classList.add('d-none')
    albumSearchResults.classList.remove('show')
}

addToAlbumButton?.addEventListener('click', async () => {
    addAlbumContainer.classList.remove('d-none')
    addAlbumInput.value = ''
    addAlbumInput.focus()
    const resp = await fetchAlbumsSearch('', 12)
    const file = await fetchFile(filePk)
    const albums = (resp.albums || []).filter(
        (a) => !file.albums.includes(a.id)
    )
    renderAlbumDropdown(albums, '')
})

addAlbumInput?.addEventListener('input', () => {
    clearTimeout(albumSearchTimer)
    albumSearchTimer = setTimeout(async () => {
        const query = addAlbumInput.value.trim()
        const resp = await fetchAlbumsSearch(query, 12)
        const file = await fetchFile(filePk)
        const albums = (resp.albums || []).filter(
            (a) => !file.albums.includes(a.id)
        )
        renderAlbumDropdown(albums, query)
    }, 250)
})

addAlbumInput?.addEventListener('blur', () => {
    setTimeout(() => {
        addAlbumInput.value = ''
        addAlbumContainer.classList.add('d-none')
        albumSearchResults.classList.remove('show')
    }, 150)
})

// End Album Badges Section
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
