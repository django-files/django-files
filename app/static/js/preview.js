// JS for embed/preview.html

document.addEventListener('DOMContentLoaded', domLoaded)

document.getElementById('openSidebar').addEventListener('click', openSidebar)
document.getElementById('closeSidebar').addEventListener('click', closeSidebar)

const previewSidebar = document.getElementById('previewSidebar')
const previewSidebarWidth = '350px'

function domLoaded() {
    if (Cookies.get('previewSidebar')) {
        previewSidebar.style.width = previewSidebarWidth
    }
}

function openSidebar() {
    previewSidebar.style.width = previewSidebarWidth
    Cookies.set('previewSidebar', 'enabled')
}

function closeSidebar() {
    previewSidebar.style.width = '0'
    Cookies.remove('previewSidebar')
}
