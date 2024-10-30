// JS for embed/preview.html

import { socket } from './socket.js'

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
        }
    }
}

function removeAlbumPress(event) {
    console.log(event.target.closest('div'))
    let album = stripAlbumID(event)
    let pk = event.target.closest('div').id.replace('albums-file-', '')
    let data = {
        album: album,
        pk: pk,
        method: 'remove_file_album',
    }
    console.log(data)
    socket.send(JSON.stringify(data))
}

function stripAlbumID(object) {
    return object.target.closest('button').id.replace('remove-album-', '')
}

$('.remove-album').on('click', removeAlbumPress)

$('.addto-album').on('click', addToAlbum)


function addToAlbum(event) {
    document.querySelector('#addto-album-list').classList.remove('d-none')
    console.log(event)

}