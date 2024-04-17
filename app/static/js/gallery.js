// Gallery JS

document.addEventListener('DOMContentLoaded', initGallery)
document.addEventListener('scroll', debounce(galleryScroll, 50))
window.addEventListener('resize', debounce(galleryScroll, 50))

const galleryContainer = document.getElementById('gallery-container')
const imageNode = document.querySelector('div.d-none img')
const faLock = document.querySelector('div.d-none .fa-lock')
const faKey = document.querySelector('div.d-none .fa-key')
const faHourglass = document.querySelector('div.d-none .fa-hourglass')

let nextPage = 1

async function initGallery() {
    console.debug('Init Gallery')
    await addNodes()
}

/**
 * Gallery onScroll Callback
 * TODO: End of page detection may need to be tweaked/improved
 * @function galleryScroll
 * @param {Event} event
 * @param {Number} buffer
 */
async function galleryScroll(event, buffer = 600) {
    console.debug(
        `galleryScroll: ${window.scrollY} > ${window.scrollMaxY - buffer}`,
        window.scrollY > window.scrollMaxY - buffer
    )
    if (
        nextPage &&
        (!window.scrollMaxY || window.scrollY > window.scrollMaxY - buffer)
    ) {
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
    console.debug('addNode')
    if (!nextPage) {
        return console.warn('No Next Page:', nextPage)
    }
    const data = await fetchGallery(nextPage)
    console.debug('data:', data)
    nextPage = data.next
    for (const file of data.files) {
        // console.debug('file:', file)

        const div = document.createElement('div')
        div.classList.add(
            'm-1',
            'rounded-1',
            'border',
            'border-3',
            'border-secondary'
        )
        div.style.position = 'relative'
        div.style.overflow = 'hidden'
        const box1 = '#919191'
        const box2 = '#495057'
        div.style.backgroundColor = '#495057'
        div.style.backgroundImage = `linear-gradient(45deg, ${box2} 25%, transparent 25%), linear-gradient(-45deg, ${box2} 25%, transparent 25%), linear-gradient(45deg, transparent 75%, ${box2} 75%), linear-gradient(-45deg, transparent 75%, ${box2} 75%)`
        div.style.backgroundImage = `linear-gradient(45deg, ${box1} 25%, transparent 25%), linear-gradient(135deg, ${box1} 25%, transparent 25%), linear-gradient(45deg, transparent 75%, ${box1} 75%), linear-gradient(135deg, transparent 75%, ${box1} 75%)`
        div.style.backgroundSize = '25px 25px'
        div.style.position = '0 0, 12.5px 0, 12.5px -12.5px, 0px 12.5px'
        div.addEventListener('mouseover', mouseOver)
        div.addEventListener('mouseout', mouseOut)

        // const img = document.createElement('img')
        // img.style.maxWidth = '512px'
        // img.style.maxHeight = '512px'
        const img = imageNode.cloneNode(true)
        img.src = file.thumb || file.raw

        const link = document.createElement('a')
        link.href = file.url
        link.title = file.name

        const topLeft = document.createElement('div')
        topLeft.classList.add(
            'gallery-text',
            'text-nowrap',
            'small',
            'd-none',
            'text-warning-emphasis'
        )
        topLeft.style.position = 'absolute'
        topLeft.style.top = '4px'
        topLeft.style.left = '6px'
        if (file.private) {
            topLeft.appendChild(faLock.cloneNode(true))
        }
        if (file.password) {
            topLeft.appendChild(faKey.cloneNode(true))
        }
        if (file.expr) {
            topLeft.appendChild(faHourglass.cloneNode(true))
        }

        const bottomLeft = document.createElement('div')
        bottomLeft.classList.add(
            'gallery-text',
            'text-nowrap',
            'small',
            'd-none'
        )
        bottomLeft.style.position = 'absolute'
        bottomLeft.style.bottom = '4px'
        bottomLeft.style.left = '6px'
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

        link.appendChild(img)
        div.appendChild(link)
        div.appendChild(topLeft)
        div.appendChild(bottomLeft)
        galleryContainer.appendChild(div)
    }
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
    const closest = event.target.closest('div')
    const divs = closest.querySelectorAll('.gallery-text')
    divs.forEach((div) => div.classList.remove('d-none'))
}

/**
 * Mouse Out Event Handler
 * @function mouseOut
 * @param {MouseEvent} event
 */
function mouseOut(event) {
    const closest = event.target.closest('div')
    const divs = closest.querySelectorAll('.gallery-text')
    divs.forEach((div) => div.classList.add('d-none'))
}

/**
 * Fetch Page from Gallery
 * @function fetchGallery
 * @param {Number} page Page Number to Fetch
 * @return {Object} JSON Response Object
 */
async function fetchGallery(page) {
    const loc = window.location.toString()
    const url = `${loc.substring(0, loc.length - 1)}/${page}/`
    const response = await fetch(url)
    return await response.json()
}

/**
 * Convert Bytes to Human Readable Bytes
 * @function formatBytes
 * @param {Number} bytes
 * @param {Number} decimals
 * @return {String}
 */
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const dm = decimals < 0 ? 0 : decimals
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i]
}
