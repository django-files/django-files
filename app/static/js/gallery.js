// Gallery JS
import {
    initFilesTable,
    faLock,
    faKey,
    faHourglass,
    faCaret,
    addDTRow,
    getCtxMenu,
    formatBytes,
} from './file-table.js'

import { fetchFiles } from './api-fetch.js'

console.debug('LOADING: gallery.js')

document.addEventListener('DOMContentLoaded', initGallery)
document.addEventListener('scroll', throttle(galleryScroll))
window.addEventListener('resize', throttle(galleryScroll))

const galleryContainer = document.getElementById('gallery-container')
// const loadingImage = document.getElementById('loading-image')

const imageNode = document.querySelector('div.d-none > img')


let nextPage = 1
let fileData = []

let fillInterval

async function initGallery() {
    console.log('Init Gallery')
    filesDataTable = initFilesTable()
    await addNodes()
    fillInterval = setInterval(fillPage, 250)
    window.dispatchEvent(new Event('resize'))
}

async function fillPage() {
    console.debug(
        'fillPage INTERVAL',
        document.body.clientHeight === document.body.scrollHeight
    )
    if (document.body.clientHeight === document.body.scrollHeight) {
        await addNodes()
    } else {
        clearInterval(fillInterval)
    }
}

$('#user').on('change', function (event) {
    let user = $(this).val()
    console.log(`user: ${user}`)
    if (user) {
        let url = new URL(location.href)
        url.searchParams.set('user', user)
        location.href = url.href
    }
})

/**
 * Gallery onScroll Callback
 * TODO: End of page detection may need to be tweaked/improved
 * @function galleryScroll
 * @param {Event} event
 * @param {Number} buffer
 */
async function galleryScroll(event, buffer = 600) {
    const maxScrollY = document.body.scrollHeight - window.innerHeight
    console.debug(
        `galleryScroll: ${window.scrollY} > ${maxScrollY - buffer}`,
        window.scrollY > maxScrollY - buffer
    )
    if (nextPage && (!maxScrollY || window.scrollY > maxScrollY - buffer)) {
        console.debug('End of Scroll')
        await addNodes()
    }
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
    const data = await fetchFiles(nextPage)
    console.debug('data:', data)
    nextPage = data.next
    for (const file of data.files) {
        // console.debug('file:', file)
        if (window.location.pathname.includes('gallery')) {
            addGalleryImage(file)
        } else if (window.location.pathname.includes('files')) {
            addDTRow(file)
        } else {
            console.error('Unknown View')
        }
    }
}

function addGalleryImage(file) {
    // console.log('addGalleryImage:', file)
    const imageExtensions = /\.(gif|ico|jpeg|jpg|png|webp)$/i
    if (!file.name.match(imageExtensions)) {
        console.debug(`Skipping non-image: ${file.name}`)
        return
    }
    // if (!file.mime.toLowerCase().startsWith('image')) {
    //     console.debug('Not Image', file)
    //     continue
    // }

    // OUTER DIV
    const outer = document.createElement('div')
    outer.classList.add(
        'gallery-outer',
        'm-1',
        'rounded-1',
        'border',
        'border-3',
        'border-secondary'
    )
    outer.style.position = 'relative'
    // TODO: hides text overflow but also the ctx menu
    // outer.style.overflow = 'hidden'
    const box1 = '#919191'
    const box2 = '#495057'
    outer.style.backgroundColor = '#495057'
    outer.style.backgroundImage = `linear-gradient(45deg, ${box2} 25%, transparent 25%), linear-gradient(-45deg, ${box2} 25%, transparent 25%), linear-gradient(45deg, transparent 75%, ${box2} 75%), linear-gradient(-45deg, transparent 75%, ${box2} 75%)`
    outer.style.backgroundImage = `linear-gradient(45deg, ${box1} 25%, transparent 25%), linear-gradient(135deg, ${box1} 25%, transparent 25%), linear-gradient(45deg, transparent 75%, ${box1} 75%), linear-gradient(135deg, transparent 75%, ${box1} 75%)`
    outer.style.backgroundSize = '25px 25px'
    outer.style.position = '0 0, 12.5px 0, 12.5px -12.5px, 0px 12.5px'
    outer.addEventListener('mouseover', mouseOver)
    outer.addEventListener('mouseout', mouseOut)

    // INNER DIV
    const inner = document.createElement('div')
    inner.classList.add('gallery-inner')
    inner.style.position = 'relative'
    inner.style.overflow = 'hidden'
    outer.appendChild(inner)

    // IMAGE AND LINK
    const link = document.createElement('a')
    link.href = file.url
    link.title = file.name
    link.target = '_blank'
    // const img = document.createElement('img')
    // img.style.maxWidth = '512px'
    // img.style.maxHeight = '512px'
    const img = imageNode.cloneNode(true)
    img.style.minHeight = '64px'
    img.src = file.thumb || file.raw
    link.appendChild(img)
    inner.appendChild(link)

    // ICONS
    const topLeft = document.createElement('div')
    topLeft.classList.add(
        'gallery-mouse',
        'd-none',
        'text-shadow',
        'text-nowrap',
        'small',
        'text-warning-emphasis'
    )
    topLeft.style.position = 'absolute'
    topLeft.style.top = '4px'
    topLeft.style.left = '6px'
    topLeft.style.pointerEvents = 'none'
    if (file.private) {
        topLeft.appendChild(faLock.cloneNode(true))
    }
    if (file.password) {
        topLeft.appendChild(faKey.cloneNode(true))
    }
    if (file.expr) {
        topLeft.appendChild(faHourglass.cloneNode(true))
    }
    inner.appendChild(topLeft)

    // TEXT
    const bottomLeft = document.createElement('div')
    bottomLeft.classList.add(
        'gallery-mouse',
        'd-none',
        'text-shadow',
        'text-nowrap',
        'small',
        'lh-sm'
    )
    bottomLeft.style.position = 'absolute'
    bottomLeft.style.bottom = '4px'
    bottomLeft.style.left = '6px'
    bottomLeft.style.pointerEvents = 'none'
    if (file.size) {
        addSpan(bottomLeft, formatBytes(file.size))
    }
    if (file.meta.PILImageWidth && file.meta.PILImageHeight) {
        const text = `${file.meta.PILImageWidth}x${file.meta.PILImageWidth}`
        addSpan(bottomLeft, text)
    }
    if (file.name) {
        addSpan(bottomLeft, file.name)
    }
    inner.appendChild(bottomLeft)

    // CTX MENU
    const ctxMenu = document.createElement('div')
    ctxMenu.classList.add('text-stroke', 'fs-4', 'ctx-menu')
    ctxMenu.style.position = 'absolute'
    ctxMenu.style.top = '-7px'
    ctxMenu.style.right = '1px'
    const toggle = document.createElement('a')
    toggle.classList.add('link-body-emphasis', 'ctx-menu')
    toggle.setAttribute('role', 'button')
    // toggle.addEventListener('click', ctxClick)
    toggle.dataset.bsToggle = 'dropdown'
    toggle.setAttribute('aria-expanded', 'false')
    toggle.appendChild(faCaret.cloneNode(true))
    ctxMenu.appendChild(toggle)
    outer.appendChild(ctxMenu)

    const menu = getCtxMenu(file)
    ctxMenu.appendChild(menu)

    // inner.appendChild(link)
    // inner.appendChild(ctxMenu)
    galleryContainer.appendChild(outer)
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
    divs.forEach((div) => div.classList.remove('d-none'))
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
