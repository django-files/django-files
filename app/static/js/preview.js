// JS for embed/preview.html

document.addEventListener('DOMContentLoaded', domLoaded)

const previewSidebar = $('#previewSidebar')
const contextPlacement = $('#contextPlacement')
const sidebarCard = $('.sidebarCard')
const openSidebarButton = $('#openSidebar')

openSidebarButton.on('click', openSidebar)
$('#closeSidebar').on('click', closeSidebar)

function domLoaded() {
    if (!Cookies.get('previewSidebar')) {
        openSidebar()
    }
}

function openSidebar() {
    previewSidebar.css('width', '360px')
    if (contextPlacement) {
        contextPlacement.css('right', '365px')
    }
    openSidebarButton.hide()
    sidebarCard.fadeIn(300)
    Cookies.remove('previewSidebar')
}

function closeSidebar() {
    previewSidebar.css('width', '0')
    if (contextPlacement) {
        contextPlacement.css('right', '60px')
    }
    openSidebarButton.show()
    sidebarCard.fadeOut(200)
    Cookies.set('previewSidebar', 'disabled', { expires: 365 })
}
