// JS for embed/preview.html

document.addEventListener('DOMContentLoaded', domLoaded)

window.addEventListener('resize', checkSize)

const previewSidebar = $('#previewSidebar')
const contextPlacement = $('#contextPlacement')
const sidebarCard = $('.sidebarCard')
const openSidebarButton = $('#openSidebar')

openSidebarButton.on('click', openSidebarCallback)
$('#closeSidebar').on('click', closeSidebarCallback)

const sidebarMaxWidth = 768

function domLoaded() {
    if (window.innerWidth >= sidebarMaxWidth) {
        if (!Cookies.get('previewSidebar')) {
            openSidebar()
        }
    }
}

// TODO: Add method to know if side bar is expanded or collapsed
function checkSize() {
    if (window.innerWidth >= sidebarMaxWidth) {
        if (!Cookies.get('previewSidebar')) {
            openSidebar()
        }
    } else {
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
    previewSidebar.css('width', '360px')
    previewSidebar.css('border-right', '1px ridge rgba(66 69 73 / 100%)')
    if (contextPlacement) {
        contextPlacement.css('right', '365px')
    }
    openSidebarButton.hide()
    sidebarCard.fadeIn(300)
}

function closeSidebar() {
    previewSidebar.css('width', '0')
    previewSidebar.css('border-right', '0px')
    if (contextPlacement) {
        contextPlacement.css('right', '60px')
    }
    openSidebarButton.show()
    sidebarCard.fadeOut(200)
}
