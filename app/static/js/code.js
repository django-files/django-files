// JS for embed/code.html

document.addEventListener('DOMContentLoaded', domLoaded)

function domLoaded() {
    if (window.matchMedia('(prefers-color-scheme: light)').matches) {
        document.getElementById('code-light').disabled = false
        document.getElementById('code-dark').disabled = true
    }
    hljs.highlightElement(document.querySelector('pre'))
}
