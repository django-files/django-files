import {
    Uppy,
    Dashboard,
    DropTarget,
    Webcam,
    Audio,
    ScreenCapture,
    XHRUpload,
} from '../dist/uppy/uppy.min.mjs'

import { fetchAlbums } from './api-fetch.js'

console.debug('LOADING: uppy.js')
console.debug('uploadUrl:', uploadUrl)

const fileUploadModal = $('#fileUploadModal')

const albumOptions = document.getElementById('upload_albums')

function getResponseError(responseText, response) {
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
    fileUploadModal.modal('show')
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


export async function getAlbums() {
    let nextPage = 1
    while (nextPage) {
        const resp = await fetchAlbums(nextPage)
        console.debug('resp:', resp)
        nextPage = resp.next
        resp.albums.forEach(createOption)
    }
}

/**
 * Create Album Option
 * @function postURL
 * @param {Object} albumEntry
 */
function createOption(album) {
    const option = document.createElement('option')
    option.textContent = album.name
    option.value = album.id
    if (selectedAlbum == album.id) {
        option.selected = true
    }
    albumOptions.options.add(option)
}

document.addEventListener('DOMContentLoaded', getAlbums)

document.getElementById("upload_inputs").addEventListener("change", function() {
    console.log(this)
    Array.from(this.elements).forEach((input) => {
        let header_name = input.id.replace('upload_', '')
        if (input.value !== 0) {
            headers[header_name] = input.value
        } else {
            headers[header_name] = ""
        }
        console.log("Selected value:", input.value);
    })
});
