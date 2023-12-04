// JS for embed/preview.html

document.addEventListener('DOMContentLoaded', domLoaded);

document.getElementById('openSidebar').addEventListener('click', openSidebar);
document.getElementById('closeSidebar').addEventListener('click', closeSidebar);

const previewSidebar = document.getElementById('previewSidebar');
const previewSidebarWidth = '350px';

const contextPlacement = document.getElementById("context-placement")

function domLoaded() {
    if (Cookies.get('previewSidebar')) {
        $(".sidebar-text").fadeOut(200);
    } else {
        previewSidebar.style.width = previewSidebarWidth;
    }
}

function openSidebar() {
    previewSidebar.style.width = previewSidebarWidth;
    if (contextPlacement) {
        contextPlacement.style.right = "355px";
    }
    Cookies.remove('previewSidebar');
    $(".openbtn").hide();
    $(".sidebar-text").fadeIn(300);
}

function closeSidebar() {
    previewSidebar.style.width = '0';
    if (contextPlacement) {
        contextPlacement.style.right = "50px";
    }
    Cookies.set('previewSidebar', 'enabled');
    $(".openbtn").show();
    $(".sidebar-text").fadeOut(200);
}
