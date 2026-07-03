// JS for Keyboard Shortcuts

const keyLocations = {
    KeyA: '/albums/',
    KeyD: '/settings/site/',
    KeyF: '/files/',
    KeyG: '/files/?view=gallery',
    KeyM: '/files/?view=map',
    KeyH: '/',
    KeyR: '/shorts/',
    KeyS: '/settings/user/',
    KeyT: '/paste/',
    KeyU: '/uppy/',
    KeyV: '/streams/',
    KeyX: '/settings/sharex/',
    KeyY: '/admin/settings/sitesettings/1/change/',
}

const tagNames = ['INPUT', 'TEXTAREA', 'SELECT', 'OPTION']

window.addEventListener('keydown', (e) => {
    // console.log('handleKeyboard:', e)
    if (
        e.altKey ||
        e.ctrlKey ||
        e.metaKey ||
        e.shiftKey ||
        e.repeat ||
        tagNames.includes(e.target.tagName) ||
        e.target.isContentEditable
    ) {
        return
    }
    if (['KeyZ', 'KeyK'].includes(e.code)) {
        $('#keybinds-modal').modal('toggle')
    } else if (keyLocations[e.code]) {
        window.location = keyLocations[e.code]
    }
})

// Clipboard upload modal
;(() => {
    const modal = document.getElementById('clipboardUploadModal')
    if (!modal) return

    const bsModal = new bootstrap.Modal(modal)
    const textSection = document.getElementById('clipboard-text-section')
    const fileSection = document.getElementById('clipboard-file-section')
    const textContent = document.getElementById('clipboard-text-content')
    const textName = document.getElementById('clipboard-text-name')
    const fileNameInput = document.getElementById('clipboard-file-name')
    const fileInfo = document.getElementById('clipboard-file-info')
    const filePreview = document.getElementById('clipboard-file-preview')
    const uploadBtn = document.getElementById('clipboard-upload-btn')

    let pendingFile = null
    let pendingText = null
    let previewObjectUrl = null

    function resetModal() {
        pendingFile = null
        pendingText = null
        textContent.value = ''
        textName.value = ''
        fileNameInput.value = ''
        fileInfo.textContent = ''
        filePreview.innerHTML = ''
        if (previewObjectUrl) {
            URL.revokeObjectURL(previewObjectUrl)
            previewObjectUrl = null
        }
        uploadBtn.disabled = false
        uploadBtn.innerHTML = '<i class="fa-solid fa-upload me-1"></i> Upload'
    }

    function showTextModal(text) {
        resetModal()
        pendingText = text
        textContent.value = text
        textSection.classList.remove('d-none')
        fileSection.classList.add('d-none')
        bsModal.show()
    }

    function showFileModal(file) {
        resetModal()
        pendingFile = file
        textSection.classList.add('d-none')
        fileSection.classList.remove('d-none')

        const kb = (file.size / 1024).toFixed(1)
        fileInfo.textContent = `${file.type || 'unknown'} · ${kb} KB`

        if (file.type.startsWith('image/')) {
            previewObjectUrl = URL.createObjectURL(file)
            const img = document.createElement('img')
            img.src = previewObjectUrl
            img.className = 'img-fluid rounded mb-2'
            img.style.maxHeight = '200px'
            filePreview.appendChild(img)
        } else {
            filePreview.innerHTML =
                '<i class="fa-regular fa-file fa-3x text-body-secondary"></i>'
        }

        const ext = file.type.split('/')[1] || 'bin'
        fileNameInput.placeholder = `clipboard.${ext}`
        bsModal.show()
    }

    uploadBtn.addEventListener('click', async () => {
        uploadBtn.disabled = true
        uploadBtn.innerHTML =
            '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Uploading…'

        try {
            const formData = new FormData()

            if (pendingText !== null) {
                const raw = textName.value.trim() || 'paste.txt'
                const filename = raw.includes('.') ? raw : `${raw}.txt`
                formData.append(
                    'file',
                    new Blob([pendingText], { type: 'text/plain' }),
                    filename
                )
            } else if (pendingFile) {
                const ext = pendingFile.type.split('/')[1] || 'bin'
                const filename =
                    fileNameInput.value.trim() || `clipboard.${ext}`
                formData.append('file', pendingFile, filename)
            } else {
                return
            }

            const resp = await fetch('/api/upload/', {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken },
                body: formData,
            })

            if (resp.ok) {
                const data = await resp.json()
                bsModal.hide()
                show_toast('Uploaded!', 'success')
                if (data.url) window.open(data.url, '_blank')
            } else {
                const err = await resp.json().catch(() => ({}))
                show_toast(err.message || 'Upload failed.', 'danger')
                uploadBtn.disabled = false
                uploadBtn.innerHTML =
                    '<i class="fa-solid fa-upload me-1"></i> Upload'
            }
        } catch {
            show_toast('Upload failed.', 'danger')
            uploadBtn.disabled = false
            uploadBtn.innerHTML =
                '<i class="fa-solid fa-upload me-1"></i> Upload'
        }
    })

    modal.addEventListener('hidden.bs.modal', resetModal)

    modal.addEventListener('show.bs.modal', (e) => {
        if (e.relatedTarget?.dataset.clipboardMode === 'text') {
            resetModal()
            textSection.classList.remove('d-none')
            fileSection.classList.add('d-none')
        }
    })

    window.addEventListener('paste', (e) => {
        if (tagNames.includes(e.target.tagName) || e.target.isContentEditable)
            return

        const items = [...(e.clipboardData?.items || [])]

        const fileItem = items.find((i) => i.kind === 'file')
        if (fileItem) {
            e.preventDefault()
            showFileModal(fileItem.getAsFile())
            return
        }

        const textItem = items.find(
            (i) => i.kind === 'string' && i.type === 'text/plain'
        )
        if (textItem) {
            e.preventDefault()
            textItem.getAsString((text) => {
                if (text.trim()) showTextModal(text)
            })
        }
    })
})()
