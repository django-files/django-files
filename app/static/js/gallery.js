// Gallery JS

document.addEventListener('DOMContentLoaded', initGallery)
document.addEventListener('scroll', debounce(galleryScroll, 50))
window.addEventListener('resize', debounce(galleryScroll, 50))

const galleryContainer = document.getElementById('gallery-container')
const imageNode = document.querySelector('div.d-none img')

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
            'border-secondary',
            'gallery-div'
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

        // const img = document.createElement('img')
        // img.style.maxWidth = '512px'
        // img.style.maxHeight = '512px'
        const img = imageNode.cloneNode(true)
        img.src = file.thumb || file.raw

        const link = document.createElement('a')
        link.href = file.url
        link.title = file.name

        const text = document.createElement('div')
        text.classList.add('text-nowrap', 'small', 'gallery-text')
        text.textContent = file.name
        text.style.position = 'absolute'
        text.style.bottom = '4px'
        text.style.left = '6px'

        link.appendChild(img)
        div.appendChild(link)
        div.appendChild(text)
        galleryContainer.appendChild(div)
        // galleryContainer.appendChild(link)
    }
}

/**
 * Fetch Next Page from Gallery
 * @function fetchGallery
 * @return {Object} JSON Response Object
 */
async function fetchGallery(page) {
    const loc = window.location.toString()
    const url = `${loc.substring(0, loc.length - 1)}/${page}/`
    const response = await fetch(url)
    return await response.json()
}
