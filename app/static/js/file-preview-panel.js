// file-preview-panel.js — Slide-in file preview panel for the gallery page

import { socket } from './socket.js'
import { initAlbumSelector } from './album-selector.js'
import { initContextMenu } from './file-context-menu.js'

const panel = document.getElementById('file-preview-panel')
const panelContent = document.getElementById('previewPanelContent')
const backdrop = document.getElementById('previewPanelBackdrop')
const panelClose = document.getElementById('previewPanelClose')

let isOpen = false
let panelLeafletMap = null
let currentFileUrl = null
let panelSocketHandler = null
let currentHeroEl = null
let currentOriginEl = null

const loadingHtml =
    '<div class="file-preview-panel-loading"><i class="fa-solid fa-spinner fa-pulse"></i></div>'

// ============================================================
// Public API
// ============================================================

export function openPanel(fileUrl, originEl = null) {
    currentFileUrl = fileUrl
    const panelUrl = `${fileUrl}${fileUrl.includes('?') ? '&' : '?'}panel=1`

    // 1. Show panel with skeleton immediately (no layout jank)
    panelContent.innerHTML = `<div class="file-preview-panel-loading" role="status" aria-live="polite"><i class="fa-solid fa-spinner fa-pulse"></i></div>`

    // Clean up any hero left over from a rapid re-open
    if (currentHeroEl) {
        currentHeroEl.remove()
        currentHeroEl = null
    }
    currentOriginEl = originEl

    let heroEl = null

    if (originEl) {
        const thumbImg = originEl.querySelector('img')
        if (thumbImg?.complete && thumbImg.naturalWidth > 0) {
            const rect = originEl.getBoundingClientRect()
            const vw = window.innerWidth
            const vh = window.innerHeight
            const t = ((rect.top / vh) * 100).toFixed(2)
            const r = (((vw - rect.right) / vw) * 100).toFixed(2)
            const b = (((vh - rect.bottom) / vh) * 100).toFixed(2)
            const l = ((rect.left / vw) * 100).toFixed(2)

            heroEl = document.createElement('div')
            heroEl.className = 'panel-hero-thumb'
            heroEl.style.clipPath = `inset(${t}% ${r}% ${b}% ${l}% round 9px)`

            const heroImg = document.createElement('img')
            heroImg.src = thumbImg.src
            // contain so the image fills its proportional area, matching what
            // the full-size image will show inside the panel
            heroImg.style.cssText =
                'width:100%;height:100%;object-fit:contain;display:block'
            heroEl.appendChild(heroImg)
            document.body.appendChild(heroEl)
            currentHeroEl = heroEl

            // Force layout so the start clip-path is committed, then animate
            heroEl.offsetHeight
            heroEl.style.transition =
                'clip-path 0.35s cubic-bezier(0.4, 0, 0.2, 1)'
            heroEl.style.clipPath = 'inset(0% 0% 0% 0% round 0px)'
        }

        // Panel opens instantly behind the hero — no slide animation
        panel.style.transition = 'none'
        panel.classList.add('open')
        panel.offsetHeight
        panel.style.transition = ''
    } else {
        panel.classList.add('open')
    }

    panel.removeAttribute('aria-hidden')
    backdrop.classList.add('active')
    document.body.style.overflow = 'hidden'
    isOpen = true

    // 2. Push preview URL to history so the browser back button closes the panel
    const returnUrl = location.href
    history.pushState({ panelOpen: true, returnUrl }, '', fileUrl)

    // 3. Fetch and render main content.
    // Wait for the hero animation to finish before injecting HTML so no layout
    // or GPU texture work happens during the clip-path transition.
    const animationDone = heroEl
        ? new Promise((r) => setTimeout(r, 350))
        : Promise.resolve()

    const fetchDone = fetch(panelUrl).then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.text()
    })

    Promise.all([fetchDone, animationDone])
        .then(([html]) => {
            // Guard: user closed panel or navigated away before fetch completed
            if (!isOpen || currentFileUrl !== fileUrl) {
                dismissHero(heroEl)
                return
            }

            panelContent.innerHTML = html
            initPanelContent(panelContent)

            // For image content initPanelImage dismisses the hero once the
            // image is decoded, creating a direct crossfade. For everything
            // else (video, text…) dismiss the hero now.
            if (!panelContent.querySelector('img.preview')) {
                dismissHero(heroEl)
            }
        })
        .catch((err) => {
            console.error('Preview panel fetch error:', err)
            // Guard: user closed panel before error state renders
            if (!isOpen || currentFileUrl !== fileUrl) {
                dismissHero(heroEl)
                return
            }

            panelContent.innerHTML = `
                <div class="file-preview-panel-loading text-danger" role="status">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    <p>Failed to load preview.</p>
                    <a href="${fileUrl}" class="btn btn-sm btn-outline-secondary mt-2">Open full page</a>
                </div>`
            dismissHero(heroEl)
        })
}

function dismissHero(heroEl) {
    if (!heroEl || heroEl !== currentHeroEl) return
    heroEl.style.transition = 'opacity 0.25s ease-in-out'
    heroEl.style.opacity = '0'
    setTimeout(() => {
        heroEl.remove()
        if (currentHeroEl === heroEl) currentHeroEl = null
    }, 250)
}

export function closePanel() {
    if (!isOpen) return
    closePanelInternal()
}

// ============================================================
// Internal close — used by buttons, keyboard, backdrop, popstate
// ============================================================

function closePanelInternal() {
    isOpen = false
    currentFileUrl = null

    // Remove any in-progress hero immediately
    if (currentHeroEl) {
        currentHeroEl.remove()
        currentHeroEl = null
    }

    const origin = currentOriginEl
    currentOriginEl = null

    if (panel.contains(document.activeElement)) document.activeElement.blur()
    panel.setAttribute('aria-hidden', 'true')
    backdrop.classList.remove('active')
    document.body.style.overflow = ''

    // Restore the gallery URL without triggering a popstate
    if (history.state?.panelOpen && history.state?.returnUrl) {
        history.replaceState(null, '', history.state.returnUrl)
    }

    // Detach WS listener
    if (panelSocketHandler) {
        socket?.removeEventListener('message', panelSocketHandler)
        panelSocketHandler = null
    }

    const thumbImg = origin?.isConnected ? origin.querySelector('img') : null

    if (thumbImg?.complete && thumbImg.naturalWidth > 0) {
        // Mirror the open animation: clear the panel immediately and use a
        // hero thumbnail div for the reverse zoom so no panel content (sidebar,
        // fixed-position elements, etc.) is visible during the animation.
        panelCleanup()
        panel.style.transition = 'none'
        panel.classList.remove('open')
        panel.offsetHeight
        panel.style.transition = ''

        const rect = origin.getBoundingClientRect()
        const vw = window.innerWidth
        const vh = window.innerHeight
        const t = ((rect.top / vh) * 100).toFixed(2)
        const r = (((vw - rect.right) / vw) * 100).toFixed(2)
        const b = (((vh - rect.bottom) / vh) * 100).toFixed(2)
        const l = ((rect.left / vw) * 100).toFixed(2)

        const closeHero = document.createElement('div')
        closeHero.className = 'panel-hero-thumb'
        closeHero.style.clipPath = 'inset(0% 0% 0% 0% round 0px)'

        const heroImg = document.createElement('img')
        heroImg.src = thumbImg.src
        heroImg.style.cssText =
            'width:100%;height:100%;object-fit:contain;display:block'
        closeHero.appendChild(heroImg)
        document.body.appendChild(closeHero)
        currentHeroEl = closeHero

        closeHero.offsetHeight
        closeHero.style.transition =
            'clip-path 0.35s cubic-bezier(0.4, 0, 0.2, 1)'
        closeHero.style.clipPath = `inset(${t}% ${r}% ${b}% ${l}% round 9px)`

        setTimeout(() => {
            closeHero.remove()
            if (currentHeroEl === closeHero) currentHeroEl = null
        }, 360)
    } else {
        // Standard slide-down (non-gallery open, or thumbnail not available)
        panel.classList.remove('open')
        setTimeout(() => {
            if (!isOpen) panelCleanup()
        }, 360)
    }
}

function panelCleanup() {
    if (panelLeafletMap) {
        panelLeafletMap.remove()
        panelLeafletMap = null
    }
    panelContent.innerHTML = loadingHtml
}

// ============================================================
// Event wiring
// ============================================================

panelClose?.addEventListener('click', closePanelInternal)
backdrop?.addEventListener('click', closePanelInternal)

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isOpen) closePanelInternal()
})

// Browser back closes the panel (we pushed a state on open)
window.addEventListener('popstate', () => {
    if (isOpen) closePanelInternal()
})

// ============================================================
// Content initialisation (runs after HTML is injected)
// ============================================================

function initPanelContent(container) {
    const root = container.querySelector('.preview-panel-root')
    if (!root) return

    const render = root.dataset.render

    // Wire all context menu actions for dynamically injected elements
    initContextMenu(container)

    // Initialize main content immediately (blocking)
    initPanelImage(container)

    // Initialize secondary features non-blocking (use requestIdleCallback)
    if ('requestIdleCallback' in window) {
        requestIdleCallback(
            () => {
                if (!isOpen) return
                initPanelSidebar(container)
                const handleAlbumBadges = initPanelAlbums(container)

                if (render === 'text' || render === 'code') {
                    initCodePreview(root)
                }

                if (root.dataset.gpsLat && root.dataset.gpsLon) {
                    initPanelMapToggle(root)
                }

                initPanelSocket(root, handleAlbumBadges)
            },
            { timeout: 1000 }
        )
    } else {
        // Fallback for browsers without requestIdleCallback
        setTimeout(() => {
            if (!isOpen) return
            initPanelSidebar(container)
            const handleAlbumBadges = initPanelAlbums(container)

            if (render === 'text' || render === 'code') {
                initCodePreview(root)
            }

            if (root.dataset.gpsLat && root.dataset.gpsLon) {
                initPanelMapToggle(root)
            }

            initPanelSocket(root, handleAlbumBadges)
        }, 0)
    }
}

// ---- Image loading ----

function initPanelImage(container) {
    const img = container.querySelector('img.preview')
    if (!img) return
    const skeleton = container.querySelector('#img-skeleton')
    // Capture at call time so a rapid re-open can't dismiss the wrong hero
    const heroEl = currentHeroEl

    // Set image to be invisible initially to prevent layout shift
    img.style.opacity = '0'
    img.style.transition = 'opacity 0.25s ease-in-out'

    const onLoad = () => {
        // Crossfade: hero fades out as the decoded image fades in together
        dismissHero(heroEl)
        if (skeleton) {
            skeleton.style.opacity = '0'
        }

        requestAnimationFrame(() => {
            img.style.opacity = '1'
        })

        // Clean up skeleton after transition
        if (skeleton) {
            setTimeout(() => {
                skeleton?.remove()
            }, 250)
        }
    }

    const onError = () => {
        if (skeleton) skeleton.remove()
        img.style.display = 'none'
        const wrapper = img.closest('.preview-wrapper')
        if (wrapper) {
            const placeholder = document.createElement('div')
            placeholder.className = 'img-error-placeholder'
            placeholder.innerHTML =
                '<i class="fa-solid fa-file-image"></i><p>Image could not be loaded.</p>'
            wrapper.appendChild(placeholder)
        }
    }

    if (img.complete) {
        if (img.naturalWidth === 0) onError()
        else onLoad()
    } else {
        // decode() waits for the image to be fully decoded before the first
        // paint, preventing the GPU texture-upload black flash on reveal.
        img.decode().then(onLoad).catch(onError)
    }
}

// ---- Sidebar ----

function initPanelSidebar(container) {
    const sidebar = container.querySelector('#preview-sidebar')
    if (!sidebar) return

    const card = container.querySelector('.preview-panel-root')
    const openBtn = container.querySelector('#openSidebar')
    const closeBtn = container.querySelector('#closeSidebar')

    let sidebarOpen = false

    function getSidebarMode() {
        return localStorage.getItem('sidebarMode') || 'overlay'
    }

    function openSidebar() {
        sidebarOpen = true
        sidebar.classList.add('open')
        card?.classList.add('sidebar-open')
        if (getSidebarMode() === 'push')
            card?.classList.add('sidebar-push-open')
        if (openBtn) openBtn.style.display = 'none'
    }

    function closeSidebar() {
        sidebarOpen = false
        sidebar.classList.remove('open')
        card?.classList.remove('sidebar-open', 'sidebar-push-open')
        if (openBtn) openBtn.style.display = ''
    }

    // Insert the overlay/push mode toggle button before the close button
    if (closeBtn) {
        const currentMode = getSidebarMode()
        const toggleBtn = document.createElement('button')
        toggleBtn.className = 'sidebar-mode-toggle'
        toggleBtn.innerHTML =
            currentMode === 'push'
                ? '<i class="fa-solid fa-layer-group"></i>'
                : '<i class="fa-solid fa-table-columns"></i>'
        toggleBtn.title =
            currentMode === 'push'
                ? 'Switch to overlay mode'
                : 'Switch to push mode'

        toggleBtn.addEventListener('click', () => {
            const next = getSidebarMode() === 'overlay' ? 'push' : 'overlay'
            localStorage.setItem('sidebarMode', next)
            if (next === 'push') {
                toggleBtn.innerHTML = '<i class="fa-solid fa-layer-group"></i>'
                toggleBtn.title = 'Switch to overlay mode'
                if (sidebarOpen) card?.classList.add('sidebar-push-open')
            } else {
                toggleBtn.innerHTML =
                    '<i class="fa-solid fa-table-columns"></i>'
                toggleBtn.title = 'Switch to push mode'
                card?.classList.remove('sidebar-push-open')
            }
        })

        closeBtn.parentElement.insertBefore(toggleBtn, closeBtn)
    }

    openBtn?.addEventListener('click', () => {
        openSidebar()
        localStorage.removeItem('panelSidebarClosed')
    })

    closeBtn?.addEventListener('click', () => {
        closeSidebar()
        localStorage.setItem('panelSidebarClosed', '1')
    })

    // Auto-open on wider screens unless user explicitly closed it
    if (
        window.innerWidth >= 768 &&
        !localStorage.getItem('panelSidebarClosed')
    ) {
        openSidebar()
    }
}

// ---- Album selector ----

function initPanelAlbums(container) {
    return initAlbumSelector(container, socket)
}

// ---- Text / code preview ----

async function initCodePreview(root) {
    const rawUrl = root.dataset.rawUrl
    if (!rawUrl) return

    const codeEl = root.querySelector('#text-preview')
    if (!codeEl) return

    if (!globalThis.hljs) {
        // Resolve the script URL from an existing static script tag if present,
        // otherwise fall back to the path used by the preview page.
        const existingScript = document.querySelector(
            'script[src*="highlight.min.js"]'
        )
        const scriptSrc =
            existingScript?.src || '/static/highlightjs/highlight.min.js'
        await new Promise((resolve, reject) => {
            const s = document.createElement('script')
            s.src = scriptSrc
            s.onload = resolve
            s.onerror = reject
            document.head.appendChild(s)
        })
    }

    try {
        const response = await fetch(rawUrl)
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const text = await response.text()
        codeEl.textContent = text

        const theme = document.documentElement.dataset.bsTheme
        const darkLink = document.querySelector('#panel-code-dark')
        const lightLink = document.querySelector('#panel-code-light')
        if (theme !== 'dark' && darkLink && lightLink) {
            darkLink.disabled = true
            lightLink.removeAttribute('disabled')
        }

        globalThis.hljs.highlightElement(codeEl)
    } catch (e) {
        codeEl.textContent = `Error loading file: ${e.message}`
    }
}

// ---- GPS map (Leaflet is already loaded on the gallery page) ----

function initPanelMapToggle(root) {
    const mapToggle = root.querySelector('#mapToggle')
    const mapCollapse = root.querySelector('#mapCollapse')
    const mapContainer = root.querySelector('#preview-map')

    if (!mapToggle || !mapCollapse || !mapContainer) return

    const L = globalThis.L
    if (!L) return

    function openMap() {
        mapCollapse.style.display = 'block'
        mapToggle.setAttribute('aria-expanded', 'true')
        mapToggle.querySelector('span').textContent = 'Hide Map'
        localStorage.setItem('panelMapOpen', '1')

        requestAnimationFrame(() => {
            if (panelLeafletMap) {
                panelLeafletMap.invalidateSize()
            } else {
                const lat = Number.parseFloat(mapContainer.dataset.lat)
                const lon = Number.parseFloat(mapContainer.dataset.lon)
                panelLeafletMap = L.map(mapContainer, {
                    zoomControl: false,
                    attributionControl: true,
                }).setView([lat, lon], 7)

                L.tileLayer(
                    'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                    {
                        attribution:
                            '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                        maxZoom: 19,
                    }
                ).addTo(panelLeafletMap)

                L.marker([lat, lon]).addTo(panelLeafletMap)
                requestAnimationFrame(() => panelLeafletMap?.invalidateSize())
            }
        })
    }

    function closeMap() {
        mapCollapse.style.display = 'none'
        mapToggle.setAttribute('aria-expanded', 'false')
        mapToggle.querySelector('span').textContent = 'Show on Map'
        localStorage.removeItem('panelMapOpen')
    }

    mapToggle.addEventListener('click', () => {
        if (mapToggle.getAttribute('aria-expanded') === 'true') closeMap()
        else openMap()
    })

    if (localStorage.getItem('panelMapOpen')) openMap()
}

// ---- WebSocket: live rename inside panel ----

function initPanelSocket(root, handleAlbumBadges) {
    if (!socket) return

    const fileId = String(root.dataset.fileId)

    panelSocketHandler = (event) => {
        if (event.data === 'pong') return
        let data
        try {
            data = JSON.parse(event.data)
        } catch {
            return
        }

        if (data.event === 'set-file-name' && String(data.id) === fileId) {
            const titleEl = root.querySelector('.card-title')
            if (titleEl) titleEl.textContent = data.name
            if (history.state?.panelOpen) {
                history.replaceState(history.state, '', data.uri)
            }
        } else if (
            data.event === 'set-file-albums' &&
            String(data.file_id) === fileId
        ) {
            handleAlbumBadges?.(data)
        }
    }

    socket.addEventListener('message', panelSocketHandler)
}
