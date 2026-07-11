// Shared JS for all settings pages (user + site)

console.debug('LOADING: settings.js')

import { socket } from './socket.js'
import { initAlbumSearchInput } from './album-selector.js'
import { fetchAlbumsSearch } from './api-fetch.js'

// -- Settings form (both pages) --
document.getElementById('settingsForm')?.addEventListener('change', saveOptions)

document
    .getElementById('uploadAvatarHookBtn')
    ?.addEventListener('click', () => {
        bootstrap.Modal.getOrCreateInstance(
            document.getElementById('avatarUploadModal')
        ).show()
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
            bootstrap.Modal.getOrCreateInstance(
                document.getElementById('create-invite-modal')
            ).hide()
            show_toast(`Invite created: ${json.invite}`, 'success')
            location.reload()
        } else {
            await fetchErrorToast(response)
        }
    })

// -- Invite delete (site page) --
document.querySelectorAll('.invite-delete').forEach((el) =>
    el.addEventListener('click', async (event) => {
        const inviteId = event.currentTarget.dataset.inviteId
        const response = await fetch(`/api/invites/${inviteId}/`, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': csrftoken },
        })
        if (response.ok) {
            document.getElementById(`invite-${inviteId}`)?.remove()
            show_toast('Invite deleted.', 'success')
        } else {
            await fetchErrorToast(response)
        }
    })
)

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

// -- OAuth Registration confirm (site page) --
const oauthRegCheckbox = document.getElementById('oauth_reg')
if (oauthRegCheckbox) {
    oauthRegCheckbox.addEventListener('change', (event) => {
        if (!event.target.checked) return
        event.stopPropagation()
        event.target.checked = false
        bootstrap.Modal.getOrCreateInstance(
            document.getElementById('oauth-reg-confirm-modal')
        ).show()
    })
}

document.getElementById('confirmOauthRegBtn')?.addEventListener('click', () => {
    bootstrap.Modal.getOrCreateInstance(
        document.getElementById('oauth-reg-confirm-modal')
    ).hide()
    oauthRegCheckbox.checked = true
    const form = document.getElementById('settingsForm')
    saveOptions({
        currentTarget: form,
        target: oauthRegCheckbox,
        type: 'change',
    })
})

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
    function selectPubAlbum(id, name) {
        pubAlbumHidden.value = id
        pubAlbumSearch.value = name
        pubAlbumHidden.dispatchEvent(new Event('change', { bubbles: true }))
    }

    // Clear hidden value when the text is erased manually
    pubAlbumSearch.addEventListener('input', () => {
        if (!pubAlbumSearch.value) {
            pubAlbumHidden.value = '0'
            pubAlbumHidden.dispatchEvent(new Event('change', { bubbles: true }))
        }
    })

    initAlbumSearchInput(pubAlbumSearch, pubAlbumResults, {
        fetchAlbums: (query) =>
            fetchAlbumsSearch(query, 8).then((r) => r.albums || []),
        onSelect: (album) => selectPubAlbum(album.id, album.name),
        onCreate: async (name) => {
            const response = await fetch('/api/album/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ name }),
            })
            if (response.ok) {
                const data = await response.json()
                const albumId = new URL(data.url).searchParams.get('album')
                selectPubAlbum(albumId, name)
            }
        },
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
        const navH =
            Number.parseFloat(
                getComputedStyle(document.documentElement).getPropertyValue(
                    '--navbar-h'
                )
            ) || 52
        document.body.dataset.bsSpy = 'scroll'
        document.body.dataset.bsTarget = '#settings-nav'
        bootstrap.ScrollSpy.getOrCreateInstance(document.body, {
            rootMargin: `-${navH}px 0px -50%`,
        })
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
    const response = await fetch(`/api/session/${sessionId}`, {
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
