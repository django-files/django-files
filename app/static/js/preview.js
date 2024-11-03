// JS for embed/preview.html

import { socket } from './socket.js'
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

////////////////////////
// Album Badges Section
let addToAlbumButton = $('.addto-album')
let addAlbumInput = $('#add-album')
let addAlbumContainer = document.querySelector('.album-add-container')


let filePk
const albumContainer = document.querySelector('.album-container')

if (albumContainer) {
    filePk = albumContainer.id.replace('albums-file-', '')
}

/**
 * Adds or removed displayed album tags on a file when a websocket album add/remove event is received.
 *
 * @param {JSON} data - JSON of albums a file was added or removed from.
 */
function handleAlbumBadges(data) {
    let container = document.querySelector('.album-container')
    if (data.removed_from) {
        for (const [key] of Object.entries(data.removed_from)) {
            document.getElementById(`album-${key}`).remove()
        }
    }
    if (data.added_to) {
        for (const [key, value] of Object.entries(data.added_to)) {
            let badge = document
                .querySelector('.d-none.album-badge')
                .cloneNode(true)
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

/**
 * Removes the file from an album when album tag X is pressed.
 *
 * @param {object} event - The triggering event.
 */
function removeAlbumPress(event) {
    let album = stripAlbumID(event)
    let data = {
        album: album,
        pk: filePk,
        method: 'remove_file_album',
    }
    console.debug(data)
    socket.send(JSON.stringify(data))
}

/**
 * Adds the file to the selected element from the album selector.
 *
 * @param {object} object - The button clicked to remove an album.
 * @returns {string} - the string representation of the respective album id.
 */
function stripAlbumID(object) {
    return object.target.closest('button').id.replace('remove-album-', '')
}

// Album list/selector event listeners
addToAlbumButton.on('click', addToAlbumList)
addAlbumInput.on('blur', minimizeToAlbum)

/**
 * Adds the file to the selected element from the album selector.
 *
 * @param {object} event - The triggering event.
 */
async function addToAlbumList(event) {
    addAlbumContainer.classList.remove('d-none')
    let albumList = await getAlbums()
    addAlbumInput.val('')
    addAlbumInput
        .autocomplete({
            source: albumList,
            select: AddToAlbum,
            minLength: 0,
            scroll: true,
            response: defaultHandle,
        })
        .focus(function () {
            $(this).autocomplete('search', $(this).val())
        })
    addAlbumInput.trigger('focus')
}

function defaultHandle(event, ui) {
    if (ui.content.length === 0) {
        ui.content.push({
            label: `Create Album "${addAlbumInput.val()}"`,
            value: addAlbumInput.val(),
        })
    }
}

/**
 * Hides the album selector when unfocused.
 *
 * @param {object} event - The triggering event.
 */
function minimizeToAlbum(event) {
    addAlbumInput.val('')
    addAlbumContainer.classList.add('d-none')
}

/**
 * Adds the file to the selected element from the album selector.
 *
 * @param {object} event - The triggering event.
 * @param {string} album_name - The name of the album.
 * @param {boolean} create - If to create the album (if the album does not exist).
 */
function AddToAlbum(event, ui) {
    let data = {
        album_name: ui.item.value,
        pk: filePk,
        method: 'add_file_album',
    }
    socket.send(JSON.stringify(data))
    addAlbumContainer.classList.add('d-none')
}

/**
 * Fetchs albums and adds them to the add to album selector.
 *
 * @returns {list} - returns a list of strings (album names)
 */
async function getAlbums() {
    let albumNames = []
    let nextPage = 1
    const file = await fetchFile(filePk)
    while (nextPage) {
        const resp = await fetchAlbums(nextPage)
        nextPage = resp.next
        /**
         * @type {Object}
         * @property {Array[Object]} albums
         */
        for (const album of resp.albums) {
            if (!file.albums.includes(album.id)) {
                albumNames.push(album.name)
            }
        }
    }
    return albumNames
}

// End Album Badges Section
////////////////////////////
