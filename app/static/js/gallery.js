// Gallery JS
import {
    initFilesTable,
    faLock,
    faKey,
    faHourglass,
    addFileTableRowsBatch,
    formatBytes,
    faCaret,
} from './file-table.js'

import { fetchFiles } from './api-fetch.js'

import { socket } from './socket.js'
import { getCtxMenuContainer } from './file-context-menu.js'

console.debug('LOADING: gallery.js')

const galleryContainer = document.getElementById('gallery-container')

const imageNode = document.querySelector('div.d-none > img')

let showGallery = document.querySelector('.show-gallery')
showGallery.onclick = changeView
let showList = document.querySelector('.show-list')
showList.onclick = changeView

let params = new URL(document.location.toString()).searchParams

let dtContainer
let nextPage = 1
let fileData = []
let fetchLock = false
let filesDataTable
let selectedFileIds = []
let skeletonObserver = null // early preemptive trigger
let skeletonFallback = null // late safety-net trigger

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

document.addEventListener('DOMContentLoaded', initGallery)

async function initGallery() {
    console.log('Init Gallery')
    filesDataTable = initFilesTable()
    dtContainer = document.querySelector('.dt-container')
    if (window.location.pathname.includes('gallery')) {
        dtContainer.hidden = true
        showGallery.style.fontWeight = 'bold'
    } else {
        showList.style.fontWeight = 'bold'
    }
    await addNodes()
    filesDataTable.on('select', function (_e, dt, _type, _indexes) {
        document.getElementById('bulk-actions').disabled = false
        console.log(`file-${dt.data().id}`)
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
    console.log(`user: ${user}`)
    if (user) {
        let url = new URL(location.href)
        url.searchParams.set('user', user)
        location.href = url.href
    }
})

/**
 * Append skeleton placeholders after the current view's content and observe
 * the first one so a fetch is triggered before the user scrolls into them.
 * @function showSkeletons
 */
function showSkeletons() {
    if (!nextPage) return

    if (!globalThis.location.pathname.includes('gallery')) {
        // List view: use an invisible sentinel element instead of visual skeletons.
        const sentinel = document.createElement('div')
        sentinel.id = 'list-scroll-sentinel'
        dtContainer.after(sentinel)

        const triggerListFetch = () => {
            if (skeletonObserver) {
                skeletonObserver.disconnect()
                skeletonObserver = null
            }
            addNodes()
        }

        skeletonObserver = new IntersectionObserver(
            (entries) => {
                if (entries[0].isIntersecting) triggerListFetch()
            },
            { rootMargin: '300px' }
        )
        skeletonObserver.observe(sentinel)

        // Sync fallback: if we're already at the bottom, fire immediately.
        const rect = sentinel.getBoundingClientRect()
        if (rect.top < window.innerHeight + 300) {
            triggerListFetch()
        }
        return
    }

    const fragment = new DocumentFragment()
    let firstSkeleton = null
    let lastSkeleton = null
    for (let i = 0; i < 16; i++) {
        const outer = tmplOuter.cloneNode(false)
        outer.id = `gallery-skeleton-${i}`
        outer.classList.add('m-1')

        const inner = tmplInner.cloneNode(false)
        inner.style.minWidth = '256px'
        inner.style.minHeight = '256px'

        const shimmer = document.createElement('div')
        shimmer.classList.add('img-skeleton')

        inner.appendChild(shimmer)
        outer.appendChild(inner)
        fragment.appendChild(outer)
        if (i === 0) firstSkeleton = outer
        lastSkeleton = outer
    }
    galleryContainer.appendChild(fragment)

    if (!firstSkeleton) return

    // Single shared trigger — fetchLock inside addNodes() is the only
    // anti-spam guard, so all paths funnel through it safely.
    function triggerFetch() {
        if (skeletonObserver) {
            skeletonObserver.disconnect()
            skeletonObserver = null
        }
        if (skeletonFallback) {
            skeletonFallback.disconnect()
            skeletonFallback = null
        }
        addNodes()
    }

    // Early observer: large rootMargin fires while the first skeleton is still
    // off-screen, preemptively starting the fetch before the user sees any
    // placeholder content.
    skeletonObserver = new IntersectionObserver(
        (entries) => {
            if (entries[0].isIntersecting) triggerFetch()
        },
        { rootMargin: '800px' }
    )
    skeletonObserver.observe(firstSkeleton)

    // Late fallback: watches the last skeleton at 0px margin. Fires only when
    // the user has actually scrolled into the bottom of the placeholder batch —
    // catches fast scrollers who passed the early trigger before it could fire.
    if (lastSkeleton) {
        skeletonFallback = new IntersectionObserver(
            (entries) => {
                if (entries[0].isIntersecting) triggerFetch()
            },
            { rootMargin: '0px' }
        )
        skeletonFallback.observe(lastSkeleton)
    }

    // Sync fallback: if the user is already past the early trigger zone when
    // showSkeletons() runs (e.g., arrived at the bottom mid-fetch), the async
    // IO callback will never fire — call addNodes() directly.
    const rect = firstSkeleton.getBoundingClientRect()
    if (rect.top < window.innerHeight + 800) {
        triggerFetch()
    }
}

/**
 * Remove all skeleton placeholders and disconnect the observer.
 * @function hideSkeletons
 */
function hideSkeletons() {
    if (skeletonObserver) {
        skeletonObserver.disconnect()
        skeletonObserver = null
    }
    if (skeletonFallback) {
        skeletonFallback.disconnect()
        skeletonFallback = null
    }
    document
        .querySelectorAll('[id^="gallery-skeleton-"]')
        .forEach((el) => el.remove())
    document.getElementById('list-scroll-sentinel')?.remove()
}

/**
 * Add Next Page Nodes to Container
 * TODO: Move the CSS to gallery.css
 *       Use HTML Templates and .cloneNode
 * @function addNodes
 */
async function addNodes() {
    console.debug('addNodes:', nextPage)
    if (!nextPage) {
        return console.warn('No Next Page:', nextPage)
    }
    if (!fetchLock) {
        // Disconnect the observer so it doesn't re-fire while fetching,
        // but leave the skeleton cards in the DOM so the user can see
        // there is more content coming while the request is in flight.
        if (skeletonObserver) {
            skeletonObserver.disconnect()
            skeletonObserver = null
        }
        filesDataTable.processing(true)
        fetchLock = true
        const data = await fetchFiles(nextPage, 25, params.get('album'))
        console.debug('data:', data)
        slideshowCallback(data)
        nextPage = data.next
        fileData.push(...data.files)
        // Data is ready — remove skeletons and render real cards.
        hideSkeletons()
        if (window.location.pathname.includes('gallery')) {
            data.files.forEach((file) => addGalleryFile(file))
        } else if (!window.location.pathname.includes('files')) {
            console.error('Unknown View')
        }
        // Add all rows to DataTables in one batch and draw once
        addFileTableRowsBatch(data.files)
        filesDataTable.processing(false)
        fetchLock = false
        showSkeletons()
    } else {
        console.debug('Another files fetch in progress waiting.')
    }
}

/**
 * Route a file to the appropriate gallery renderer.
 * @function addGalleryFile
 */
function addGalleryFile(file, top = false) {
    if (file.mime?.startsWith('video/')) {
        addGalleryVideo(file, top)
    } else {
        addGalleryImage(file, top)
    }
}

/**
 * Build the shared outer/inner card structure for a gallery item — outer div,
 * inner div, status icons, text labels, context menu, checkbox — and append it
 * to the gallery container. Returns { outer, inner } so callers can insert the
 * media element (image or video canvas) before calling this.
 * @function buildGalleryCard
 * @param {Object} file
 * @param {boolean} top
 * @returns {{ outer: HTMLElement, inner: HTMLElement }}
 */
function buildGalleryCard(file, top = false) {
    // OUTER DIV
    const outer = tmplOuter.cloneNode(false)
    outer.id = `gallery-image-${file.id}`
    outer.addEventListener('mouseover', mouseOver)
    outer.addEventListener('mouseout', mouseOut)

    // INNER DIV
    const inner = tmplInner.cloneNode(true)
    outer.appendChild(inner)

    // ICONS
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

    // TEXT LABELS
    const bottomLeft = tmplLabels.cloneNode(true)
    buildImageLabels(file, bottomLeft)
    inner.appendChild(bottomLeft)

    // CTX MENU
    const ctxMenu = tmplCtx.cloneNode(true)
    const toggle = tmplCtxToggle.cloneNode(true)
    toggle.appendChild(faCaret.cloneNode(true))
    ctxMenu.appendChild(toggle)
    outer.appendChild(ctxMenu)
    const menu = getCtxMenuContainer(file)
    menu.style.zIndex = '1'
    ctxMenu.appendChild(menu)

    // CHECKBOX
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
    // console.log('addGalleryImage:', file)
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

    // Pre-size the image using known dimensions to prevent layout jumping
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

    // Skeleton overlay — fades out when image finishes loading
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
    // Insert media before icons/labels (prepend to inner)
    inner.prepend(skeleton, link)
}

/**
 * Add a video file to the gallery using its server-generated thumbnail image.
 * If no thumbnail exists yet (still being generated), a static placeholder
 * is shown instead. Clicking either state opens the file preview page.
 * @function addGalleryVideo
 */
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

    if (file.thumb) {
        const img = imageNode.cloneNode(true)
        img.width = maxThumbSize
        img.height = maxThumbSize

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
                const placeholder = document.createElement('div')
                placeholder.className = 'img-error-placeholder'
                placeholder.innerHTML = '<i class="fa-solid fa-file-video"></i>'
                inner.appendChild(placeholder)
            },
            { once: true }
        )
        img.src = file.thumb
        link.appendChild(img)
        // prepend order determines stacking: link(in-flow) at base,
        // skeleton(abs) covers it while loading, playBtn(abs) surfaces after fade
        inner.prepend(playBtn, skeleton, link)
    } else {
        // Thumbnail not yet generated — show a static placeholder
        inner.style.minWidth = `${maxThumbSize}px`
        inner.style.minHeight = `${maxThumbSize}px`
        const placeholder = document.createElement('div')
        placeholder.className = 'img-error-placeholder'
        placeholder.innerHTML = '<i class="fa-solid fa-file-video"></i>'
        link.appendChild(placeholder)
        inner.prepend(playBtn, link)
    }
}

/**
 * Generate Gallery Checkbox HTML Object
 * @function buildGalleryCheckbox
 * @returns checkbox
 */
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

/**
 * Add Text Span and BR to Parent Element
 * @function addSpan
 * @param {HTMLElement} parent
 * @param {String} textContent
 */
function addSpan(parent, textContent) {
    let span = document.createElement('span')
    span.textContent = textContent
    parent.appendChild(span)
    parent.appendChild(document.createElement('br'))
}

/**
 * Mouse Over Event Handler
 * @function mouseOver
 * @param {MouseEvent} event
 */
function mouseOver(event) {
    if (isTouch) return
    event.currentTarget._mouseEls?.forEach((el) =>
        el.classList.remove('d-none')
    )
}

/**
 * Mouse Out Event Handler
 * @function mouseOut
 * @param {MouseEvent} event
 */
function mouseOut(event) {
    // TODO: Fix mouse out detection when mousing over ctx menu
    if (event.target.closest('a')?.classList.contains('ctx-menu')) return
    event.currentTarget._mouseEls?.forEach((el) => el.classList.add('d-none'))
}

/**
 * Render an array of files into the gallery in chunks, yielding to the browser
 * between each batch so it can paint incrementally instead of blocking.
 * @function renderGalleryChunked
 * @param {Array} files
 * @param {number} chunkSize
 * @param {Function} [onComplete]
 */
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
    if (event.currentTarget.innerHTML === 'List') {
        galleryContainer.replaceChildren()
        dtContainer.hidden = false
        window.history.replaceState({}, null, '/files/' + '?' + params)
        showList.style.fontWeight = 'bold'
        showGallery.style.fontWeight = 'normal'
        filesDataTable.responsive.recalc()
    } else {
        // Capture selected IDs before switching so they survive the re-render
        selectedFileIds = []
        filesDataTable.rows('.selected').every(function () {
            selectedFileIds.push(this.data().id)
        })
        dtContainer.hidden = true
        window.history.replaceState({}, null, '/gallery/' + '?' + params)
        galleryContainer.replaceChildren()
        showList.style.fontWeight = 'normal'
        showGallery.style.fontWeight = 'bold'
        renderGalleryChunked(fileData, 20, showSkeletons)
    }
}

socket?.addEventListener('message', function (event) {
    if (event.data === 'pong') return
    if (window.location.pathname.includes('gallery')) {
        let data = JSON.parse(event.data)
        if (data.event === 'file-delete') {
            fileDeleteGallery(data.id)
        } else if (data.event === 'file-new') {
            // file-table handles added file already so we just need to add to gallery if its the view
            if (window.location.pathname.includes('gallery')) {
                addGalleryFile(data, true)
            }
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
    bottomLeft.classList.add('lh-sm')
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
