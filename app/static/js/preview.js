// JS for embed/preview.html

document.addEventListener('DOMContentLoaded', domLoaded)

document.getElementById('open-nav').addEventListener('click', openSidebar)
document.getElementById('close-nav').addEventListener('click', closeSidebar)

const previewSidebar = document.getElementById('previewSidebar')

function domLoaded() {
    if (Cookies.get('previewSidebar') === 'open') {
        previewSidebar.style.width = '350px'
    }
}

function openSidebar() {
    previewSidebar.style.width = '350px'
    Cookies.set('previewSidebar', 'open')
}

function closeSidebar() {
    previewSidebar.style.width = '0'
    Cookies.remove('previewSidebar')
}
