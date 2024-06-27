// JS for settings/user.html

const themeToggle = document.getElementById('theme-toggle')
const newThemeValue = document.getElementById('new-theme-value')

document.addEventListener('DOMContentLoaded', domContentLoaded)
themeToggle.addEventListener('click', toggleThemeSwitch)

/**
 * DOMContentLoaded Callback
 * @function domContentLoaded
 */
async function domContentLoaded() {
    console.debug('DOMContentLoaded: settings-user.js')
    const storedTheme = localStorage.getItem('theme')
    console.debug('storedTheme:', storedTheme)
    if (storedTheme && storedTheme !== 'auto') {
        themeToggle.checked = true
    }
    const prefers = window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'Light'
        : 'Dark'
    console.log('prefers:', prefers)
    newThemeValue.textContent = prefers
}

function toggleThemeSwitch() {
    const query = window.matchMedia('prefers-color-scheme: dark')
    console.info('data-bs-theme-value', query)

    const storedTheme = localStorage.getItem('theme')
    console.info('storedTheme:', storedTheme)
    let prefers
    if (storedTheme) {
        prefers = storedTheme === 'light' ? 'dark' : 'light'
        console.debug('reverting to auto theme')
        localStorage.removeItem('theme')
    } else {
        prefers = window.matchMedia('(prefers-color-scheme: dark)').matches
            ? 'light'
            : 'dark'
        console.log('forcing opposite theme:', prefers)
        localStorage.setItem('theme', prefers)
    }
    document.documentElement.setAttribute('data-bs-theme', prefers)
}
