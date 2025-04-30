// JS for embed/code.html

document.addEventListener('DOMContentLoaded', domLoaded)

const resultEl = document.querySelector('pre')

function domLoaded() {
    const url = document.getElementById('raw-url').textContent?.trim()
    console.log(`url: ${url}`)
    fetch(url)
        .then((response) => {
            return response.text()
        })
        .then(loadResult)
        .catch((e) => {
            console.log(`e: ${e.message}`)
        })
}

function loadResult(result) {
    console.log(`result: ${result}`)
    resultEl.textContent = result
    hljs.highlightElement(resultEl)
    if (window.matchMedia('(prefers-color-scheme: light)').matches) {
        document.getElementById('code-light').disabled = false
        document.getElementById('code-dark').disabled = true
    }
}
