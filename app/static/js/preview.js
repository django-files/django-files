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
    $(".card-body").fadeOut(200);
}

function openSidebar() {
    previewSidebar.style.width = previewSidebarWidth
    Cookies.set('previewSidebar', 'enabled')
    $(".openbtn").hide();
    $(".card-body").fadeIn(300);
}

function closeSidebar() {
    previewSidebar.style.width = '0'
    Cookies.remove('previewSidebar')
    $(".openbtn").show();
    $(".card-body").fadeOut(200);
}
