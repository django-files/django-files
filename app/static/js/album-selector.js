import { fetchAlbumsSearch, fetchFile } from './api-fetch.js'

/**
 * Low-level album search dropdown.
 * Wires debounced search, dropdown rendering, and blur to a text input + results list.
 *
 * @param {HTMLInputElement} inputEl
 * @param {HTMLElement} resultsEl  - a <ul class="dropdown-menu">
 * @param {object} options
 * @param {function} options.fetchAlbums  - async (query: string) => Album[]
 * @param {function} options.onSelect     - (album: {id, name}) => void
 * @param {function} [options.onCreate]   - async (name: string) => void  (omit to hide "Create" option)
 */
export function initAlbumSearchInput(
    inputEl,
    resultsEl,
    { fetchAlbums, onSelect, onCreate }
) {
    function renderDropdown(albums, query) {
        resultsEl.innerHTML = ''
        for (const album of albums) {
            const li = document.createElement('li')
            const a = document.createElement('a')
            a.className = 'dropdown-item'
            a.href = '#'
            a.textContent = album.name
            a.addEventListener('mousedown', (e) => {
                e.preventDefault()
                onSelect(album)
                resultsEl.classList.remove('show')
            })
            li.appendChild(a)
            resultsEl.appendChild(li)
        }
        if (onCreate && query) {
            if (albums.length) {
                const dividerLi = document.createElement('li')
                dividerLi.innerHTML = '<hr class="dropdown-divider">'
                resultsEl.appendChild(dividerLi)
            }
            const createLi = document.createElement('li')
            const a = document.createElement('a')
            a.className = 'dropdown-item'
            a.href = '#'
            a.innerHTML = `<i class="fa-solid fa-plus me-1"></i> Create <strong>${query}</strong>`
            a.addEventListener('mousedown', async (e) => {
                e.preventDefault()
                await onCreate(query)
                resultsEl.classList.remove('show')
            })
            createLi.appendChild(a)
            resultsEl.appendChild(createLi)
        }
        resultsEl.classList.toggle(
            'show',
            albums.length > 0 || !!(onCreate && query)
        )
    }

    let timer

    inputEl.addEventListener('focus', async () => {
        const query = inputEl.value.trim()
        renderDropdown(await fetchAlbums(query), query)
    })

    inputEl.addEventListener('input', () => {
        clearTimeout(timer)
        timer = setTimeout(async () => {
            const query = inputEl.value.trim()
            renderDropdown(await fetchAlbums(query), query)
        }, 250)
    })

    inputEl.addEventListener('blur', () => {
        setTimeout(() => resultsEl.classList.remove('show'), 150)
    })
}

/**
 * Wires the add-album button, search input, and blur behaviour shared by both
 * single-file and bulk selectors. Automatically calls closeInput() after each
 * onSelect/onCreate so the callbacks don't have to.
 */
function wireAlbumAddInput(container, { fetchAlbums, onSelect, onCreate }) {
    const addToAlbumButton = container.querySelector('.addto-album')
    const addAlbumInput = container.querySelector('.album-search-input')
    const addAlbumContainer = container.querySelector('.album-add-container')
    const albumSearchResults = container.querySelector('.album-search-results')

    function closeInput() {
        addAlbumInput.value = ''
        addAlbumContainer.classList.add('d-none')
        albumSearchResults.classList.remove('show')
    }

    addToAlbumButton?.addEventListener('click', () => {
        addAlbumContainer.classList.remove('d-none')
        addAlbumInput.value = ''
        addAlbumInput.focus()
    })

    addAlbumInput?.addEventListener('blur', () => setTimeout(closeInput, 150))

    initAlbumSearchInput(addAlbumInput, albumSearchResults, {
        fetchAlbums,
        onSelect: (album) => {
            onSelect(album)
            closeInput()
        },
        onCreate: onCreate
            ? (name) => {
                  onCreate(name)
                  closeInput()
              }
            : undefined,
    })
}

/**
 * Full album badge selector for the file preview sidebar.
 * Returns a handleAlbumBadges(data) callback for the websocket handler.
 */
export function initAlbumSelector(container, socket) {
    const albumContainer = container.querySelector('.album-container')
    if (!albumContainer) return null

    const filePk = albumContainer.id.replace('albums-file-', '')

    function removeAlbumPress(event) {
        const albumId = event.target
            .closest('button')
            .id.replace('remove-album-', '')
        socket.send(
            JSON.stringify({
                album: albumId,
                pk: filePk,
                method: 'remove_file_album',
            })
        )
    }

    container
        .querySelectorAll('.remove-album')
        .forEach((el) => el.addEventListener('click', removeAlbumPress))

    wireAlbumAddInput(container, {
        fetchAlbums: async (query) => {
            const [resp, file] = await Promise.all([
                fetchAlbumsSearch(query, 12),
                fetchFile(filePk),
            ])
            return (resp.albums || []).filter(
                (a) => !file.albums.includes(a.id)
            )
        },
        onSelect: (album) => {
            socket.send(
                JSON.stringify({
                    album_name: album.name,
                    pk: filePk,
                    method: 'add_file_album',
                })
            )
        },
        onCreate: (name) => {
            socket.send(
                JSON.stringify({
                    album_name: name,
                    pk: filePk,
                    method: 'add_file_album',
                })
            )
        },
    })

    function handleAlbumBadges(data) {
        if (data.removed_from) {
            for (const [key] of Object.entries(data.removed_from)) {
                container.querySelector(`#album-${key}`)?.remove()
            }
        }
        if (data.added_to) {
            const addGroup = container.querySelector('.addto-album-group')
            for (const [key, value] of Object.entries(data.added_to)) {
                const span = document.createElement('span')
                span.className =
                    'badge rounded-pill text-bg-primary ps-2 file-album-active'
                span.id = `album-${key}`
                span.innerHTML = `
                    <a class="text-reset text-decoration-none p-0" href="/files/?view=gallery&album=${key}" title="${value}">${value} </a>
                    <button id="remove-album-${key}" class="btn p-0 mt-0 remove-album">
                        <i class="fa-solid fa-xmark text-small remove-album"></i>
                    </button>`
                span.querySelector('.remove-album').addEventListener(
                    'click',
                    removeAlbumPress
                )
                addGroup.before(span)
            }
        }
    }

    return handleAlbumBadges
}

/**
 * Bulk album badge selector. Shows badges for the union of albums across all
 * selected files. Badges show a count "(n)" when only n of the selected files
 * are in that album. Add/remove dispatch bulk-edit-file-albums WS messages.
 *
 * @param {HTMLElement} container  - the #modal-album-badge-ui element
 * @param {WebSocket}   socket
 * @param {number[]}    pks        - selected file IDs
 */
export function initBulkAlbumSelector(container, socket, pks) {
    const albumContainer = container.querySelector('.album-container')

    function removeAlbumPress(event) {
        const albumId = Number(
            event.target.closest('button').id.replace('remove-album-', '')
        )
        socket.send(
            JSON.stringify({
                method: 'bulk-edit-file-albums',
                pks,
                albums: [albumId],
                action: 'remove',
            })
        )
        albumContainer.querySelector(`#album-${albumId}`)?.remove()
    }

    container
        .querySelectorAll('.remove-album')
        .forEach((el) => el.addEventListener('click', removeAlbumPress))

    function addBadge(id, name) {
        const existing = albumContainer.querySelector(`#album-${id}`)
        if (existing) {
            const a = existing.querySelector('a')
            a.textContent = name + ' '
            a.title = name
            return
        }
        const addGroup = albumContainer.querySelector('.addto-album-group')
        const span = document.createElement('span')
        span.className =
            'badge rounded-pill text-bg-primary ps-2 ms-1 file-album-active pb-0 pt-0 mt-1 mb-1'
        span.id = `album-${id}`
        span.innerHTML = `
            <a class="text-reset text-decoration-none p-0" href="/files/?view=gallery&album=${id}" title="${name}">${name} </a>
            <button id="remove-album-${id}" class="btn p-0 mt-0 remove-album">
                <i class="fa-solid fa-xmark text-small remove-album"></i>
            </button>`
        span.querySelector('.remove-album').addEventListener(
            'click',
            removeAlbumPress
        )
        addGroup.before(span)
    }

    wireAlbumAddInput(container, {
        fetchAlbums: async (query) => {
            const resp = await fetchAlbumsSearch(query, 12)
            return resp.albums || []
        },
        onSelect: (album) => {
            socket.send(
                JSON.stringify({
                    method: 'bulk-edit-file-albums',
                    pks,
                    albums: [album.id],
                    action: 'add',
                })
            )
            addBadge(album.id, album.name)
        },
        onCreate: (name) => {
            socket.send(
                JSON.stringify({
                    method: 'bulk-edit-file-albums',
                    pks,
                    album_name: name,
                    action: 'add',
                })
            )
        },
    })
}
