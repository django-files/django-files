// JS for embed/preview.html

document.addEventListener('DOMContentLoaded', domLoaded)

const previewSidebar = document.getElementById('previewSidebar')
const contextPlacement = document.getElementById('contextPlacement')

const sidebarCard = $('#sidebarCard')
const openSidebarButton = $('#openSidebar')

openSidebarButton.on('click', openSidebar)
$('#closeSidebar').on('click', closeSidebar)

function domLoaded() {
    if (!Cookies.get('previewSidebar')) {
        openSidebar()
    }
}

function openSidebar() {
    previewSidebar.style.width = '360px'
    if (contextPlacement) {
        contextPlacement.style.right = '365px'
    }
    openSidebarButton.hide()
    sidebarCard.fadeIn(300)
    Cookies.remove('previewSidebar')
}

function closeSidebar() {
    previewSidebar.style.width = '0'
    if (contextPlacement) {
        contextPlacement.style.right = '60px'
    }
    openSidebarButton.show()
    sidebarCard.fadeOut(200)
    Cookies.set('previewSidebar', 'disabled', { expires: 365 })
}
