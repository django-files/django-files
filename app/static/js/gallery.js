// Gallery JS

document.addEventListener('DOMContentLoaded', initGallery)
document.addEventListener('scroll', throttle(galleryScroll))
window.addEventListener('resize', throttle(galleryScroll))

const galleryContainer = document.getElementById('gallery-container')
const tableContainer = document.getElementById('table-container')
const loadingImage = document.getElementById('loading-image')
const imageNode = document.querySelector('div.d-none img')
const faLock = document.querySelector('div.d-none .fa-lock')
const faKey = document.querySelector('div.d-none .fa-key')
const faHourglass = document.querySelector('div.d-none .fa-hourglass')
const faCaret = document.querySelector('div.d-none .fa-square-caret-down')

// const siteUrl = document.getElementById('site_url')?.value

let nextPage = 1
let fileData = []

const filesTable = $('#files-table')

let dataTables
const dataTablesOptions = {
    order: [0, 'desc'],
    processing: true,
    saveState: true,
    pageLength: -1,
    lengthMenu: [
        [10, 25, 50, 100, 250, -1],
        [10, 25, 50, 100, 250, 'All'],
    ],
    columnDefs: [
        { targets: 0, width: '5%' },
        { targets: 2, type: 'file-size' },
        {
            targets: 4,
            render: DataTable.render.datetime('DD MMM YYYY, kk:mm'),
        },
        { targets: [6, 7, 9], orderable: false },
    ],
}

let fillInterval

async function initGallery() {
    console.log('Init Gallery')
    if (filesView === 'list') {
        filesDataTable = filesTable.DataTable(dataTablesOptions)
    }
    await addNodes()
    fillInterval = setInterval(fillPage, 250)
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
        // await addNodes()
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
    const data = await fetchGallery(nextPage)
    // console.debug('data:', data)
    nextPage = data.next
    for (const file of data.files) {
        // console.debug('file:', file)
        if (filesView === 'gallery') {
            const imageExtensions = /\.(gif|ico|jpeg|jpg|png|webp)$/i
            if (!file.name.match(imageExtensions)) {
                console.debug(`Skipping non-image: ${file.name}`)
                continue
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
        } else if (filesView === 'list') {
            addFilesDTRow(file)
        }
    }
}

function addFilesDTRow(file) {
    console.log(`Adding File ${file.name} to DT`)
    if (file.password) {
        pw = true
    } else {
        pw = false
    }

    // CTX MENU
    const ctxMenu = document.createElement('div')
    const toggle = document.createElement('a')
    toggle.classList.add('link-body-emphasis', 'ctx-menu')
    toggle.setAttribute('role', 'button')
    toggle.dataset.bsToggle = 'dropdown'
    toggle.setAttribute('aria-expanded', 'false')
    toggle.setAttribute(
        'class',
        'btn btn-secondary file-context-dropdown my-0 py-0'
    )
    toggle.innerHTML = '<i class="fa-regular fa-square-caret-down"></i>'
    ctxMenu.appendChild(toggle)

    const menu = getCtxMenu(file)
    ctxMenu.appendChild(menu)

    let new_row = [
        file.id,
        file.name,
        file.size,
        file.mime,
        file.date,
        file.expr,
        pw,
        getPrivateFileHTML(file.private),
        file.view,
        ctxMenu.outerHTML,
    ]
    console.log(new_row)
    filesDataTable.row.add(new_row).draw()
}

function getPrivateFileHTML(status) {
    if (status) {
        return '<i class="fa-solid fa-lock text-warning-emphasis privateStatus"></i></td>'
    } else {
        return '<i class="fa-solid fa-lock text-warning-emphasis privateStatus" style="display: none"></i></td>'
    }
}

/**
 * Get Context Menu for File
 * @function getCtxMenu
 * @param {Object} file
 * @return {HTMLElement}
 */
function getCtxMenu(file) {
    // console.debug('getCtxMenu:', file)

    const menu = document.getElementById('ctx-menu-').cloneNode(true)
    menu.id = `ctx-menmu-${file.id}`

    const copyShare = menu.querySelector('.copy-share-link')
    copyShare.dataset.clipboardText = file.url

    const copyRaw = menu.querySelector('.copy-raw-link')
    copyRaw.dataset.clipboardText = file.raw

    const openRaw = menu.querySelector('.open-raw')
    openRaw.href = file.raw

    menu.querySelector('a[download=""]').setAttribute('download', file.raw)
    // const downloadFile = menu.querySelector('.download-file')

    return menu
}

// function ctxClick(event) {
//     console.debug('ctxClick', event)
//     event.preventDefault()
//     // let ctx = document.getElementById('ctx-menu-')
// }

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

/**
 * Fetch Page from Gallery
 * @function fetchGallery
 * @param {Number} page Page Number to Fetch
 * @param {Number} amount Numer of Files to Fetch
 * @return {Object} JSON Response Object
 */
async function fetchGallery(page) {
    if (!page) {
        return console.warn('no page', page)
    }
    const url = `${window.location.origin}/api/pages/${page}/`
    const response = await fetch(url)
    const json = await response.json()
    nextPage = json.next
    if (!nextPage) {
        noNextCallback()
    }
    fileData.push(...json.files)
    console.log('fileData:', fileData)
    return json
}

function noNextCallback() {
    console.log('noNextCallback')
    loadingImage.classList.add('d-none')
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
