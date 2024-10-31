// JS for embed/preview.html

import { socket } from './socket.js'
import { createOption } from './file-context-menu.js'
import { fetchFile, fetchAlbums } from './api-fetch.js'

document.addEventListener('DOMContentLoaded', domLoaded)
window.addEventListener('resize', checkSize)

const previewSidebar = $('#previewSidebar')
const contextPlacement = $('#contextPlacement')
const sidebarCard = $('.sidebarCard')
const openSidebarButton = $('#openSidebar')
openSidebarButton.on('click', openSidebarCallback)
$('#closeSidebar').on('click', closeSidebarCallback)

const sidebarMaxWidth = 768
let sidebarOpen = false

function domLoaded() {
    if (window.innerWidth >= sidebarMaxWidth) {
        if (!Cookies.get('previewSidebar')) {
            openSidebar()
        }
    }
}

function checkSize() {
    if (window.innerWidth >= sidebarMaxWidth) {
        if (!sidebarOpen) {
            if (!Cookies.get('previewSidebar')) {
                openSidebar()
            }
        }
    } else if (sidebarOpen) {
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
    previewSidebar.css('width', '360px')
    previewSidebar.css('border-right', '1px ridge rgba(66 69 73 / 100%)')
    if (contextPlacement) {
        contextPlacement.css('right', '365px')
    }
    openSidebarButton.hide()
    sidebarCard.fadeIn(300)
}

function closeSidebar() {
    sidebarOpen = false
    previewSidebar.css('width', '0')
    previewSidebar.css('border-right', '0px')
    if (contextPlacement) {
        contextPlacement.css('right', '60px')
    }
    openSidebarButton.show()
    sidebarCard.fadeOut(200)
}

function renameFile(data) {
    let fileName = document.getElementsByClassName('card-title')[0]
    fileName.innerHTML = data.name
    window.history.pushState({}, '', data.uri)
}

socket?.addEventListener('message', function (event) {
    let data = JSON.parse(event.data)
    if (data.event === 'set-file-name') {
        renameFile(data)
    } else if (data.event === 'set-file-albums') {
        handleAlbumBadges(data)
    }
})

///////////////
// Album Badges

function handleAlbumBadges(data) {
    let container = document.querySelector('.album-container')
    if (data.removed_from) {
        for (const [key, value] of Object.entries(data.removed_from)) {
            document.getElementById(`album-${key}`).remove()
        }
    }
    if (data.added_to) {
        for (const [key, value] of Object.entries(data.added_to)) {
            let badge = document
                .querySelector('.d-none.album-badge')
                .cloneNode(true)
            console.log(badge)
            badge.id = `album-${key}`
            let button = badge.querySelector('.remove-album')
            button.id = `remove-album-${key}`
            button.onclick = removeAlbumPress
            let label = badge.querySelector('.album-badge-label')
            label.href = `/gallery?album=${key}`
            label.innerHTML = value
            badge.classList.remove('d-none')
            container.appendChild(badge)
            container.appendChild(document.querySelector('.addto-album-group'))
        }
    }
}

$('.remove-album').on('click', removeAlbumPress)

let filePk = document
    .querySelector('.album-container')
    .id.replace('albums-file-', '')
let addToAlbumButton = $('.addto-album')
addToAlbumButton.on('click', addToAlbumList)

let listInput = document.querySelector('.add-album-list-input')
let albumDataList = document.querySelector('#add-album-list')

listInput.addEventListener('change', AddToAlbum)

function removeAlbumPress(event) {
    console.log(event.target.closest('div'))
    let album = stripAlbumID(event)

    let data = {
        album: album,
        pk: filePk,
        method: 'remove_file_album',
    }
    console.log(data)
    socket.send(JSON.stringify(data))
}

function stripAlbumID(object) {
    return object.target.closest('button').id.replace('remove-album-', '')
}

function addToAlbumList(event) {
    listInput.classList.remove('d-none')
    listInput.value = ''
    listInput.focus()
    listInput.onblur = minimizeToAlbum
    console.log(event)
    getAlbums()
}

function minimizeToAlbum(event) {
    listInput.classList.add('d-none')
}

function AddToAlbum(event, album_name = null, create = false) {
    console.log(this.value)
    let options = Array.from(albumDataList.options).map(
        (option) => option.value
    )
    if (!options.includes(this.value)) {
        console.debug('creating album')
        create = true
        album_name = this.value
    }
    let data = {
        create: create,
        album_name: album_name,
        album: this.value,
        pk: filePk,
        method: 'add_file_album',
    }
    console.debug(data)
    socket.send(JSON.stringify(data))
}

async function getAlbums() {
    albumDataList.innerHTML = '' // Clear the list to start fresh every search
    let nextPage = 1
    const file = await fetchFile(filePk)
    console.debug('file:', file)
    while (nextPage) {
        const resp = await fetchAlbums(nextPage)
        console.debug('resp:', resp)
        nextPage = resp.next
        /**
         * @type {Object}
         * @property {Array[Object]} albums
         */
        for (const album of resp.albums) {
            console.debug('album:', album)
            if (!file.albums.includes(album.id)) {
                console.debug('actually displaying')
                let option = createOption(album.id, album.name)
                if (file.albums.includes(album.id)) {
                    option.selected = true
                }
                albumDataList.appendChild(option)
            }
        }
    }
}
