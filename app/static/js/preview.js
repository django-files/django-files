// JS for embed/preview.html

document.addEventListener('DOMContentLoaded', domLoaded)

document.getElementById('open-nav').addEventListener('click', openSidebar)
document.getElementById('close-nav').addEventListener('click', closeSidebar)

const previewSidebar = document.getElementById('previewSidebar')
const sidebarWidth = '350px'

function domLoaded() {
    if (Cookies.get('previewSidebar') === 'open') {
        previewSidebar.style.width = sidebarWidth
    }
}

function openSidebar() {
    previewSidebar.style.width = sidebarWidth
    Cookies.set('previewSidebar', 'open')
}

function closeSidebar() {
    previewSidebar.style.width = '0'
    Cookies.remove('previewSidebar')
}
