// JS for embed/preview.html

document.addEventListener('DOMContentLoaded', domLoaded);

document.getElementById('openSidebar').addEventListener('click', openSidebar);
document.getElementById('closeSidebar').addEventListener('click', closeSidebar);

const previewSidebar = document.getElementById('previewSidebar');
const previewSidebarWidth = '350px';

function domLoaded() {
    if (Cookies.get('previewSidebar')) {
        previewSidebar.style.width = previewSidebarWidth;
    } else {
        $(".sidebar-text").fadeOut(200);
    }
}

function openSidebar() {
    previewSidebar.style.width = previewSidebarWidth;
    document.getElementById("context-placement").style.right = "355px";
    Cookies.set('previewSidebar', 'enabled');
    $(".openbtn").hide();
    $(".sidebar-text").fadeIn(300);
}

function closeSidebar() {
    previewSidebar.style.width = '0';
    document.getElementById("context-placement").style.right = "50px";
    Cookies.remove('previewSidebar');
    $(".openbtn").show();
    $(".sidebar-text").fadeOut(200);
}
