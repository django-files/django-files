// Click-to-edit file name and description in the preview sidebar.
// Shared by preview.js (full-page embed) and file-preview-panel.js (gallery panel).

export function initFileEditables(root, socket) {
    initNameEdit(root, socket)
    initDescriptionEdit(root, socket)

    return function handleFileDescription(data) {
        const descEl = root.querySelector('.file-desc')
        if (descEl && document.activeElement !== descEl) {
            descEl.textContent = data.description
        }
    }
}

function selectContents(el) {
    const range = document.createRange()
    range.selectNodeContents(el)
    const selection = window.getSelection()
    selection.removeAllRanges()
    selection.addRange(range)
}

function initNameEdit(root, socket) {
    const nameEl = root.querySelector('.card-title.file-editable')
    if (!nameEl) return
    let originalName = nameEl.textContent.trim()

    nameEl.addEventListener('dblclick', function () {
        if (this.isContentEditable) return
        originalName = this.textContent.trim()
        this.contentEditable = 'true'
        this.focus()
        selectContents(this)
    })

    nameEl.addEventListener('blur', function () {
        if (!this.isContentEditable) return
        this.contentEditable = 'false'
        const newName = this.textContent.trim()
        // Revert display; the set-file-name WS event applies the new name on
        // success (rename can fail server-side, e.g. name already taken)
        this.textContent = originalName
        if (newName && newName !== originalName) {
            socket?.send(
                JSON.stringify({
                    method: 'set-file-name',
                    pk: Number(this.dataset.fileId),
                    name: newName,
                })
            )
        }
    })

    nameEl.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault()
            this.blur()
        } else if (e.key === 'Escape') {
            this.textContent = originalName
            this.blur()
        }
    })
}

function initDescriptionEdit(root, socket) {
    const descEl = root.querySelector('.file-desc.file-editable')
    if (!descEl) return
    let originalDesc = descEl.textContent.trim()

    descEl.addEventListener('focus', function () {
        originalDesc = this.textContent.trim()
    })

    descEl.addEventListener('blur', function () {
        const newDesc = this.textContent.trim()
        // Normalize so a cleared field is truly :empty and shows the placeholder
        this.textContent = newDesc
        if (newDesc !== originalDesc) {
            originalDesc = newDesc
            socket?.send(
                JSON.stringify({
                    method: 'set-file-description',
                    pk: Number(this.dataset.fileId),
                    description: newDesc,
                })
            )
        }
    })

    descEl.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            e.preventDefault()
            this.blur()
        } else if (e.key === 'Escape') {
            this.textContent = originalDesc
            this.blur()
        }
    })
}
