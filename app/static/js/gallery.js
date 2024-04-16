// Gallery JS

document.addEventListener('DOMContentLoaded', initGallery)

window.addEventListener('resize', debounce(galleryScroll, 50))
document.addEventListener('scroll', debounce(galleryScroll, 50))

const container = document.getElementById('gallery-container')
const source = document.querySelector('div.d-none img')

let fileData

async function initGallery() {
    console.log('Init Gallery')
    fileData = await fetchGallery()
    console.log('fileData:', fileData)
    const initial = 10

    // Fill screen with nodes until the scroll bar appears
    addNode(initial)
}

function galleryScroll() {
    console.log('galleryScroll')
    if (fileData.length) {
        if (!window.scrollMaxY || window.scrollY > window.scrollMaxY - 30) {
            console.log('END OF SCROLL')
            addNode(5)
        }
    }
}

function addNode(count) {
    console.log('addNode')
    for (let i = 0; i < count; i++) {
        const data = fileData.pop()
        const node = source.cloneNode(true)
        node.src = `/raw/${data.fields.name}`
        container.appendChild(node)
    }
}

async function fetchGallery() {
    const loc = window.location.toString()
    const url = `${loc.substring(0, loc.length - 1)}-files/`
    // console.debug('url:', url)
    const response = await fetch(url)
    let data = await response.json()
    data = data.reverse()
    // console.debug('data:', data)
    return data
}
