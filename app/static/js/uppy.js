import {
    Uppy,
    Dashboard,
    DropTarget,
    Webcam,
    Audio,
    ScreenCapture,
    XHRUpload,
} from '../dist/uppy/uppy.min.mjs'

import { fetchAlbumsSearch } from './api-fetch.js'
import { initAlbumSearchInput } from './album-selector.js'

console.debug('LOADING: uppy.js')
console.debug('uploadUrl:', uploadUrl)

const fileUploadModal = $('#fileUploadModal')

const albumHidden = document.getElementById('upload_albums')

function getResponseError(responseText, _response) {
    return new Error(JSON.parse(responseText).message)
}

const headers = {
    'X-CSRFToken': $('input[name=csrfmiddlewaretoken]').val(),
}

const searchParams = new URLSearchParams(window.location.search)
const selectedAlbum = Number(searchParams.get('album'))
// Make sure we set album header since we only update header on album choice change
if (selectedAlbum) {
    headers.albums = selectedAlbum
}

const uppy = new Uppy({ debug: false, autoProceed: false })
    .use(Dashboard, {
        inline: true,
        theme: 'auto',
        target: '#uppy',

        showProgressDetails: true,
        showLinkToFileUploadResult: true,
        autoOpenFileEditor: true,
        proudlyDisplayPoweredByUppy: false,
        note: 'Django Files Upload',
        height: 380,
        width: '100%',
        metaFields: [
            { id: 'name', name: 'Name', placeholder: 'File Name' },
            {
                id: 'Expires-At',
                name: 'Expires At',
                placeholder: 'File Expiration Time.',
            },
            {
                id: 'info',
                name: 'Info',
                placeholder: 'Information about the file.',
            },
        ],
        browserBackButtonClose: false,
    })
    .use(Webcam, { target: Dashboard })
    .use(Audio, { target: Dashboard })
    .use(ScreenCapture, { target: Dashboard })
    .use(XHRUpload, {
        endpoint: uploadUrl,
        headers,
        getResponseError: getResponseError,
    })
    .use(DropTarget, {
        target: document.body,
    })

uppy.on('file-added', (file) => {
    console.debug('file-added:', file)
    const uppyEl = document.getElementById('uppy')
    if (fileUploadModal.length && fileUploadModal[0].contains(uppyEl)) {
        fileUploadModal.modal('show')
    }
})

uppy.on('complete', (fileCount) => {
    console.debug('complete:', fileCount)
    if (typeof fileUploadModal !== 'undefined') {
        fileUploadModal?.modal('hide')
    }
})

uppy.on('upload-error', (file, error, response) => {
    console.debug('upload-error:', response.body.message)
})

uppy.on('error', (error) => {
    console.debug('error:', error)
})

fileUploadModal?.on('hidden.bs.modal', (event) => {
    console.debug('hidden.bs.modal:', event)
    uppy.cancelAll()
})

function selectAlbum(id, name) {
    albumHidden.value = id
    document.getElementById('upload_album_search').value = name
    headers.albums = id || ''
}

document.addEventListener('DOMContentLoaded', async () => {
    const searchInput = document.getElementById('upload_album_search')
    const resultsEl = document.getElementById('upload_album_results')
    if (!searchInput || !resultsEl) return

    initAlbumSearchInput(searchInput, resultsEl, {
        fetchAlbums: (query) =>
            fetchAlbumsSearch(query, 8).then((r) => r.albums || []),
        onSelect: (album) => selectAlbum(album.id, album.name),
        onCreate: async (name) => {
            const response = await fetch('/api/album/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': $('input[name=csrfmiddlewaretoken]').val(),
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ name }),
            })
            if (response.ok) {
                const data = await response.json()
                const albumId = new URL(data.url).searchParams.get('album')
                selectAlbum(albumId, name)
            }
        },
    })

    searchInput.addEventListener('input', () => {
        if (!searchInput.value) {
            albumHidden.value = '0'
            headers.albums = ''
        }
    })

    if (selectedAlbum) {
        const resp = await fetchAlbumsSearch('', 100)
        const album = (resp.albums || []).find((a) => a.id === selectedAlbum)
        if (album) selectAlbum(album.id, album.name)
    }
})
