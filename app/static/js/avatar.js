// JS for Avatar Upload

import {
    Uppy,
    Dashboard,
    DropTarget,
    // ImageEditor,
    Webcam,
    XHRUpload,
} from '/static/uppy/uppy.min.js'

console.debug('LOADING: avatar.js')
console.debug('uploadUrl:', uploadUrl)

const uppy = new Uppy({
    debug: true,
    autoProceed: false,
    restrictions: {
        allowedFileTypes: ['.jpeg', '.jpg', '.png', '.gif'],
        maxNumberOfFiles: 1,
    },
})
    .use(Dashboard, {
        inline: true,
        theme: 'auto',
        target: '#uppy',
        showProgressDetails: true,
        showLinkToFileUploadResult: true,
        autoOpenFileEditor: true,
        proudlyDisplayPoweredByUppy: false,
        note: 'Django Files Avatar Upload',
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
    .use(Webcam, { target: Dashboard, modes: ['picture'] })
    .use(XHRUpload, {
        endpoint: uploadUrl,
        headers: {
            'X-CSRFToken': $('input[name=csrfmiddlewaretoken]').val(),
            avatar: 'True',
        },
    })
    .use(DropTarget, {
        target: document.body,
    })
// .use(ImageEditor, { target: Dashboard })

uppy.on('file-added', (file) => {
    console.debug('file-added:', file)
    fileUploadModal.modal('show')
})

uppy.on('upload-success', (fileCount) => {
    console.debug('upload-success:', fileCount)
    // fileUploadModal?.modal('hide')
    window.location.reload(true)
})

uppy.on('upload-error', (file, error, response) => {
    console.debug('upload-error:', response.body.message)
})

fileUploadModal?.on('hidden.bs.modal', (event) => {
    console.debug('hidden.bs.modal:', event)
    uppy.cancelAll()
    // uppy.close({ reason: 'user' })
})

uppy.on('error', (error) => {
    console.warn('error:', error)
})

uppy.on('info-visible', function () {
    fileUploadModal.modal('show')
    // const state = uppy.getState()
    // console.warn('state:', state)
    // const { info } = uppy.getState()
    // console.warn('info:', info)
    // setTimeout(() => {
    //     console.warn('info.type:', info.type)
    //     console.log(`${info.message} ${info.details}`)
    //     if (info.type === 'error') {
    //         showToast(info.message, 'danger')
    //     }
    // }, 250)
})
