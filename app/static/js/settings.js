// Shared JS for all settings pages (user + site)

console.debug('LOADING: settings.js')

import { socket } from './socket.js'

// -- Settings form (both pages) --
document.getElementById('settingsForm')?.addEventListener('change', saveOptions)

// -- Discord webhook delete (user page) --
let hookID
document.querySelectorAll('.deleteDiscordHookBtn').forEach((el) =>
    el.addEventListener('click', (event) => {
        hookID = event.currentTarget.dataset.hookId
        bootstrap.Modal.getOrCreateInstance(
            document.getElementById('deleteDiscordHookModal')
        ).show()
    })
)

document
    .getElementById('uploadAvatarHookBtn')
    ?.addEventListener('click', () => {
        bootstrap.Modal.getOrCreateInstance(
            document.getElementById('avatarUploadModal')
        ).show()
    })

document
    .getElementById('confirmDeleteDiscordHookBtn')
    ?.addEventListener('click', async () => {
        const response = await fetch(`/ajax/delete/hook/${hookID}/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrftoken },
        })
        const modal = bootstrap.Modal.getOrCreateInstance(
            document.getElementById('deleteDiscordHookModal')
        )
        modal.hide()
        if (response.ok) {
            const table = document.getElementById('discordWebhooksTable')
            const rowCount = table?.querySelectorAll('tr').length ?? 0
            document.getElementById(`webhook-${hookID}`)?.remove()
            if (rowCount <= 2) table?.remove()
            show_toast(`Webhook ${hookID} Successfully Removed.`, 'success')
        } else {
            await fetchErrorToast(response)
        }
    })

// -- Invites form (site page) --
document
    .getElementById('invitesForm')
    ?.addEventListener('submit', async (event) => {
        event.preventDefault()
        const form = event.currentTarget
        const data = Object.fromEntries(new FormData(form))
        const response = await fetch(form.action, {
            method: form.method.toUpperCase(),
            body: JSON.stringify(data),
            headers: {
                'X-CSRFToken': csrftoken,
                'Content-Type': 'application/json',
            },
        })
        if (response.ok) {
            const json = await response.json()
            alert(`Invite Created: ${json.invite}`)
            location.reload()
        } else {
            await fetchErrorToast(response)
        }
    })

// -- Check for update (site page) --
document.getElementById('check-for-update')?.addEventListener('click', () => {
    socket.send(JSON.stringify({ method: 'check-for-update' }))
})

// -- Sessions (site page) --
const deleteSessionsModalEl = document.getElementById('delete-sessions-modal')
const deleteAllSessionsBtn = document.getElementById('delete-all-sessions')
deleteAllSessionsBtn?.addEventListener('click', (e) => deleteSession(e, true))
document
    .querySelectorAll('[data-session]')
    .forEach((el) => el.addEventListener('click', (e) => deleteSession(e)))

// -- Login background (site page) --
const backgroundPicture = document.getElementById('background_picture_group')
const backgroundVideo = document.getElementById('background_video_group')
document
    .getElementsByName('login_background')
    .forEach((el) =>
        el.addEventListener('change', (event) =>
            updateBackgroundInput(event.target.value)
        )
    )

// -- Public uploads toggle (site page) --
document.getElementById('pub_load')?.addEventListener('change', (event) => {
    document
        .getElementById('public-album')
        .classList.toggle('d-none', !event.target.checked)
})

// -- Public album typeahead --
const pubAlbumHidden = document.getElementById('pub_album')
const pubAlbumSearch = document.getElementById('pub_album_search')
const pubAlbumResults = document.getElementById('pub_album_results')

if (pubAlbumSearch) {
    let albumSearchTimer

    async function fetchAlbums(query) {
        const url = query
            ? `/api/albums/1/8/?search=${encodeURIComponent(query)}`
            : '/api/albums/1/8/'
        const response = await fetch(url)
        if (!response.ok) return []
        const data = await response.json()
        return data.albums || []
    }

    function renderAlbumResults(albums, query) {
        pubAlbumResults.innerHTML = ''
        for (const album of albums) {
            const li = document.createElement('li')
            const a = document.createElement('a')
            a.className = 'dropdown-item'
            a.href = '#'
            a.textContent = album.name
            a.dataset.id = album.id
            a.addEventListener('mousedown', (e) => {
                e.preventDefault()
                pubAlbumHidden.value = album.id
                pubAlbumSearch.value = album.name
                pubAlbumResults.classList.remove('show')
                pubAlbumHidden.dispatchEvent(
                    new Event('change', { bubbles: true })
                )
            })
            li.appendChild(a)
            pubAlbumResults.appendChild(li)
        }
        if (query) {
            if (albums.length) {
                const divider = document.createElement('li')
                divider.innerHTML = '<hr class="dropdown-divider">'
                pubAlbumResults.appendChild(divider)
            }
            const createLi = document.createElement('li')
            const a = document.createElement('a')
            a.className = 'dropdown-item'
            a.href = '#'
            a.innerHTML = `<i class="fa-solid fa-plus me-1"></i> Create <strong>${query}</strong>`
            a.addEventListener('mousedown', async (e) => {
                e.preventDefault()
                const response = await fetch('/api/album/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrftoken,
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ name: query }),
                })
                if (response.ok) {
                    const data = await response.json()
                    const albumId = new URL(data.url).searchParams.get('album')
                    pubAlbumHidden.value = albumId
                    pubAlbumSearch.value = query
                    pubAlbumResults.classList.remove('show')
                    pubAlbumHidden.dispatchEvent(
                        new Event('change', { bubbles: true })
                    )
                }
            })
            createLi.appendChild(a)
            pubAlbumResults.appendChild(createLi)
        }
        pubAlbumResults.classList.toggle('show', albums.length > 0 || !!query)
    }

    pubAlbumSearch.addEventListener('focus', async () => {
        const query = pubAlbumSearch.value.trim()
        const albums = await fetchAlbums(query)
        renderAlbumResults(albums, query)
    })

    pubAlbumSearch.addEventListener('input', () => {
        if (!pubAlbumSearch.value) {
            pubAlbumHidden.value = '0'
            pubAlbumHidden.dispatchEvent(new Event('change', { bubbles: true }))
        }
        clearTimeout(albumSearchTimer)
        albumSearchTimer = setTimeout(async () => {
            const query = pubAlbumSearch.value.trim()
            const albums = await fetchAlbums(query)
            renderAlbumResults(albums, query)
        }, 250)
    })

    pubAlbumSearch.addEventListener('blur', () => {
        setTimeout(() => pubAlbumResults.classList.remove('show'), 150)
    })

    // Init: load current album name if ID is set
    document.addEventListener('DOMContentLoaded', async () => {
        const currentId = pubAlbumHidden?.value
        if (currentId && currentId !== '0') {
            const response = await fetch(`/api/album/${currentId}`)
            if (response.ok) {
                const album = await response.json()
                if (album.name) pubAlbumSearch.value = album.name
            }
        }
    })
}

// -- DOMContentLoaded: init --
document.addEventListener('DOMContentLoaded', () => {
    console.debug('DOMContentLoaded: settings.js')
    // ScrollSpy for sticky sidebar nav
    if (document.getElementById('settings-nav')) {
        document.body.dataset.bsSpy = 'scroll'
        document.body.dataset.bsTarget = '#settings-nav'
        document.body.dataset.bsSmoothScroll = 'true'
        bootstrap.ScrollSpy.getOrCreateInstance(document.body)
    }
    // Init login background input visibility
    const selected = document.querySelector(
        'input[name="login_background"]:checked'
    )
    if (selected) updateBackgroundInput(selected.value)
})

// -- Functions --

function applyValidationErrors(form, data) {
    for (const el of form.elements) {
        if (Object.hasOwn(data, el.name)) {
            const invalid = document.getElementById(`${el.name}-invalid`)
            if (invalid) invalid.textContent = data[el.name]
            el.classList.add('is-invalid')
        }
    }
}

async function saveOptions(event) {
    const excludes = ['data-bs-theme-value']
    if (excludes.includes(event.target.id)) {
        return console.debug('ignored setting:', event.target.id)
    }
    console.debug(`saveOptions: ${event.type}`, event)
    const form = event.currentTarget
    const response = await fetch(globalThis.location.pathname, {
        method: 'POST',
        body: new FormData(form),
        headers: { 'X-CSRFToken': csrftoken },
    })
    if (!response.ok) {
        if (response.status === 400) {
            applyValidationErrors(form, await response.json())
        }
        show_toast(`${response.status}: ${response.statusText}`, 'danger')
        return
    }
    const data = await response.json()
    console.debug('success:', data, event)
    if (data.reload) {
        location.reload()
    } else if (event.target.type === 'text') {
        event.target.classList.add('is-valid')
        setTimeout(() => event.target.classList.remove('is-valid'), 3000)
    }
}

async function deleteSession(event, all = false) {
    console.debug('deleteSession:', event)
    const sessionId = all ? 'all' : event.currentTarget.dataset.session
    const siteUrl = document.getElementById('site_settings-site_url').value
    const response = await fetch(`${siteUrl}/api/session/${sessionId}`, {
        method: 'DELETE',
    })
    if (response.status === 201) {
        if (all) {
            document
                .getElementById('sessions-table')
                .querySelector('tbody')
                .querySelectorAll('tr:not(.table-active)')
                .forEach((el) => el.remove())
            bootstrap.Modal.getOrCreateInstance(deleteSessionsModalEl).hide()
            const code = deleteSessionsModalEl.querySelector('code')
            const count = +code.textContent - 1
            code.textContent = count
            if (count < 1) deleteAllSessionsBtn.classList.add('d-none')
        } else {
            event.currentTarget.closest('tr').remove()
        }
        show_toast('Session Deleted.')
    } else if (response.status === 404) {
        show_toast('Session Not Found.')
    } else if (response.status === 400) {
        show_toast(await response.text())
    } else {
        show_toast('Error Deleting Session.', 'danger')
    }
}

function updateBackgroundInput(value) {
    backgroundPicture?.classList.toggle('d-none', value !== 'picture')
    backgroundVideo?.classList.toggle('d-none', value !== 'video')
}

async function fetchErrorToast(response) {
    let message
    try {
        const data = await response.json()
        message = data.error
            ? `${response.status}: ${data.error}`
            : `${response.status}: ${response.statusText}`
    } catch {
        message = `${response.status}: ${response.statusText}`
    }
    show_toast(message, 'danger')
}
