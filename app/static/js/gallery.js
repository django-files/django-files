// Gallery JS
import {
    initFilesTable,
    faLock,
    faKey,
    faHourglass,
    addFileTableRow,
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
let skeletonObserver = null

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
    // fillInterval = setInterval(fillPage, 250)
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
    if (!nextPage || !globalThis.location.pathname.includes('gallery')) return

    for (let i = 0; i < 8; i++) {
        const card = document
            .querySelector('.d-none .gallery-outer')
            .cloneNode(false)
        card.id = `gallery-skeleton-${i}`
        card.classList.add(
            'gallery-skeleton-card',
            'm-1',
            'rounded-1',
            'border',
            'border-3',
            'border-secondary'
        )
        galleryContainer.appendChild(card)
    }

    const firstSkeleton = document.getElementById('gallery-skeleton-0')
    if (firstSkeleton) {
        skeletonObserver = new IntersectionObserver(
            (entries) => {
                if (entries[0].isIntersecting) {
                    skeletonObserver.disconnect()
                    skeletonObserver = null
                    addNodes()
                }
            },
            { rootMargin: '300px' }
        )
        skeletonObserver.observe(firstSkeleton)
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
    document
        .querySelectorAll('[id^="gallery-skeleton-"]')
        .forEach((el) => el.remove())
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
        hideSkeletons()
        filesDataTable.processing(true)
        fetchLock = true
        const data = await fetchFiles(nextPage, 25, params.get('album'))
        console.debug('data:', data)
        slideshowCallback(data)
        nextPage = data.next
        fileData.push(...data.files)
        for (const file of data.files) {
            // console.debug('file:', file)
            if (window.location.pathname.includes('gallery')) {
                addGalleryFile(file)
                addFileTableRow(file)
            } else if (window.location.pathname.includes('files')) {
                addFileTableRow(file)
            } else {
                console.error('Unknown View')
            }
        }
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
    const outer = document
        .querySelector('.d-none .gallery-outer')
        .cloneNode(false)
    outer.id = `gallery-image-${file.id}`
    outer.addEventListener('mouseover', mouseOver)
    outer.addEventListener('mouseout', mouseOut)

    // INNER DIV
    const inner = document
        .querySelector('.d-none .gallery-inner')
        .cloneNode(true)
    outer.appendChild(inner)

    // ICONS
    const topLeft = document
        .querySelector('.d-none .image-icons')
        .cloneNode(true)
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
    const bottomLeft = document
        .querySelector('.d-none .image-labels')
        .cloneNode(true)
    buildImageLabels(file, bottomLeft)
    inner.appendChild(bottomLeft)

    // CTX MENU
    const ctxMenu = document
        .querySelector('.d-none .gallery-ctx')
        .cloneNode(true)
    const toggle = document
        .querySelector('.d-none .gallery-ctx-toggle')
        .cloneNode(true)
    toggle.appendChild(faCaret.cloneNode(true))
    ctxMenu.appendChild(toggle)
    outer.appendChild(ctxMenu)
    const menu = getCtxMenuContainer(file)
    menu.style.zIndex = '1'
    ctxMenu.appendChild(menu)

    // CHECKBOX
    inner.appendChild(buildGalleryCheckbox(file))

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
 * Add a video file to the gallery. The raw video is NOT loaded until the card
 * scrolls into view, at which point a single frame is extracted via Canvas and
 * used as a thumbnail. Clicking the card opens the file preview page.
 * @function addGalleryVideo
 */
function addGalleryVideo(file, top = false) {
    const maxThumbSize = 256
    const { outer, inner } = buildGalleryCard(file, top)

    inner.style.minWidth = `${maxThumbSize}px`
    inner.style.minHeight = `${maxThumbSize}px`

    // CANVAS (frame thumbnail)
    const canvas = document.createElement('canvas')
    canvas.width = maxThumbSize
    canvas.height = maxThumbSize
    canvas.style.width = '100%'
    canvas.style.height = '100%'
    canvas.style.display = 'block'

    // LINK wraps canvas
    const link = document.createElement('a')
    link.classList.add('image-link')
    link.href = file.url
    link.title = file.name
    link.target = '_blank'
    link.appendChild(canvas)

    // SKELETON overlay — fades out after frame extraction
    const skeleton = document.createElement('div')
    skeleton.classList.add('img-skeleton')

    // PLAY BUTTON overlay
    const playBtn = document.createElement('div')
    playBtn.classList.add('video-play-overlay')
    playBtn.innerHTML =
        '<i class="fa-solid fa-circle-play fa-3x text-white"></i>'

    // Insert media before icons/labels (prepend to inner)
    inner.prepend(playBtn, skeleton, link)

    // Lazy frame extraction — fires when card is about to scroll into view
    const frameObserver = new IntersectionObserver(
        (entries) => {
            if (entries[0].isIntersecting) {
                frameObserver.disconnect()
                extractVideoFrame(file.raw, canvas, skeleton)
            }
        },
        { rootMargin: '200px' }
    )
    frameObserver.observe(outer)
}

/**
 * Extract the first frame of a video via Canvas and render it into the given
 * canvas element. Uses preload="metadata" so only a small initial segment is
 * fetched, not the full video. Fades out the skeleton when done.
 * @function extractVideoFrame
 * @param {String} src - raw video URL
 * @param {HTMLCanvasElement} canvas
 * @param {HTMLElement} skeleton
 */
function extractVideoFrame(src, canvas, skeleton) {
    console.debug('extractVideoFrame:', src)
    const video = document.createElement('video')
    video.preload = 'metadata'
    video.muted = true
    video.playsInline = true
    video.crossOrigin = 'anonymous'

    video.addEventListener(
        'loadeddata',
        () => {
            video.currentTime = 0
        },
        { once: true }
    )

    video.addEventListener(
        'seeked',
        () => {
            try {
                const ctx = canvas.getContext('2d')
                // letterbox the frame inside the square canvas
                const vw = video.videoWidth || canvas.width
                const vh = video.videoHeight || canvas.height
                const scale = Math.min(canvas.width / vw, canvas.height / vh)
                const drawW = vw * scale
                const drawH = vh * scale
                const dx = (canvas.width - drawW) / 2
                const dy = (canvas.height - drawH) / 2
                ctx.fillStyle = '#000'
                ctx.fillRect(0, 0, canvas.width, canvas.height)
                ctx.drawImage(video, dx, dy, drawW, drawH)
            } catch (err) {
                console.warn('extractVideoFrame canvas error:', err)
            }
            // release video resources
            video.src = ''
            video.load()
            // fade out skeleton
            if (skeleton) {
                skeleton.style.transition = 'opacity 0.3s'
                skeleton.style.opacity = '0'
                skeleton.addEventListener(
                    'transitionend',
                    () => skeleton.remove(),
                    {
                        once: true,
                    }
                )
            }
        },
        { once: true }
    )

    video.addEventListener(
        'error',
        () => {
            console.warn('extractVideoFrame load error:', src)
            if (skeleton) skeleton.remove()
        },
        { once: true }
    )

    video.src = src
    video.load()
}

/**
 * Generate Gallery Checkbox HTML Object
 * @function buildGalleryCheckbox
 * @returns checkbox
 */
function buildGalleryCheckbox(file) {
    const checkbox = document
        .querySelector('.d-none .gallery-checkbox')
        .cloneNode(true)
    if (isTouchDevice()) {
        checkbox.classList.remove('d-none')
    }
    checkbox.id = `checkbox-${file.id}`
    if (selectedFileIds.includes(file.id)) {
        checkbox.checked = true
        checkbox.classList.remove('gallery-mouse')
        checkbox.classList.remove('gallery-mouse')
        checkbox.classList.remove('d-none')
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
    // console.debug('mouseOver:', event)
    // console.debug('mouse: Show')
    const closest = event.target.closest('div')
    const divs = closest.querySelectorAll('.gallery-mouse')
    if (!isTouchDevice()) {
        divs.forEach((div) => div.classList.remove('d-none'))
    }
}

/**
 * Mouse Out Event Handler
 * @function mouseOut
 * @param {MouseEvent} event
 */
function mouseOut(event) {
    // console.debug('mouseOut:', event)
    // TODO: Fix mouse out detection when mousing over ctx menu
    const link = event.target.closest('a')
    // console.debug('link:', link)
    if (link?.classList.contains('ctx-menu')) {
        // console.debug('return on ctx-menu')
        return
    }

    // console.debug('mouse: Hide')
    const closest = event.target.closest('div')
    const divs = closest.querySelectorAll('.gallery-mouse')
    divs.forEach((div) => div.classList.add('d-none'))
}

function changeView(event) {
    event.preventDefault()
    hideSkeletons()
    if (event.srcElement.innerHTML === 'List') {
        while (galleryContainer.lastChild) {
            galleryContainer.lastChild.remove()
        }
        dtContainer.hidden = false
        window.history.replaceState({}, null, '/files/' + '?' + params)
        showList.style.fontWeight = 'bold'
        showGallery.style.fontWeight = 'normal'
        filesDataTable.responsive.recalc()
    } else {
        // any time we are about to iterate grab what files are selected to transfer to next view
        selectedFileIds = []
        filesDataTable.rows('.selected').every(function () {
            selectedFileIds.push(this.data().id)
        })
        dtContainer.hidden = true
        window.history.replaceState({}, null, '/gallery/' + '?' + params)
        while (galleryContainer.lastChild) {
            galleryContainer.lastChild.remove()
        }
        fileData.forEach(function (item, _index) {
            addGalleryFile(item)
        })
        showList.style.fontWeight = 'normal'
        showGallery.style.fontWeight = 'bold'
        showSkeletons()
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
    fileData.splice(fileData.findIndex((file) => file.id === pk))
    console.log(fileData)
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

function isTouchDevice() {
    return (
        'ontouchstart' in window ||
        navigator.maxTouchPoints > 0 ||
        navigator.msMaxTouchPoints > 0
    )
}
