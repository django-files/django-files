// JS for embed/code.html

const preEl = document.querySelector('pre')
const darkStyle = document.getElementById('code-dark')
const lightStyle = document.getElementById('code-light')
const rawUrl = document.getElementById('raw-url').textContent?.trim()

console.log(`rawUrl: ${rawUrl}`)

fetch(rawUrl)
    .then((response) => {
        return response.text()
    })
    .then(loadResult)
    .catch((e) => {
        return e.message
    })

document.addEventListener('DOMContentLoaded', () => {
    console.log('DOMContentLoaded')
})

function loadResult(result) {
    console.log('loadResult')
    // console.log(`result: ${result}`)
    preEl.textContent = result
    hljs.highlightElement(preEl)
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    applyTheme(mediaQuery)
    mediaQuery.addEventListener('change', applyTheme)
}

function applyTheme(mediaQuery) {
    console.log(`applyTheme: ${mediaQuery.matches}`)
    if (mediaQuery.matches) {
        darkStyle.disabled = false
        lightStyle.disabled = true
    } else {
        darkStyle.disabled = true
        lightStyle.disabled = false
    }
}
