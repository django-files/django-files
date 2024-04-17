// Gallery JS

document.addEventListener('DOMContentLoaded', initGallery)
window.addEventListener('resize', debounce(galleryScroll, 50))
document.addEventListener('scroll', debounce(galleryScroll, 50))

const container = document.getElementById('gallery-container')
const source = document.getElementById('gallery-source')
let nextPage = 1

async function initGallery() {
    console.log('Init Gallery')
    await addNodes()
}

/**
 * Gallery onScroll Callback
 * TODO: End of page detection may need to be tweaked/improved
 * @function galleryScroll
 */
async function galleryScroll() {
    const buffer = 600
    console.debug(
        `galleryScroll: ${window.scrollY} > ${window.scrollMaxY - buffer}`,
        window.scrollY > window.scrollMaxY - buffer
    )
    if (nextPage) {
        if (!window.scrollMaxY || window.scrollY > window.scrollMaxY - buffer) {
            console.debug('End of Scroll')
            await addNodes()
        }
    }
}

/**
 * Add Next Page Nodes to Container
 * @function addNodes
 */
async function addNodes() {
    console.log('addNode')
    if (!nextPage) {
        return console.warn('No Next Page:', nextPage)
    }
    const data = await fetchGallery(nextPage)
    nextPage = data.next
    console.log('data:', data)
    for (const file of data.files) {
        const img = source.querySelector('img').cloneNode(true)
        img.src = file.thumb
        const link = document.createElement('a')
        link.href = file.url
        link.appendChild(img)
        link.title = file.name
        container.appendChild(link)
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
