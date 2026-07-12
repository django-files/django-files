// Shared tag-chip rendering and editing, used by the album Manage Tags
// modal, the create-album modal, and the bulk tags modal.

/**
 * Render removable tag chips into a container.
 * @param {Element} container - Chip parent; existing .tag-chip children are replaced.
 * @param {string[]} tags - Tag names to render.
 * @param {(tag: string) => void} onRemove - Called with the tag when its X is clicked.
 * @param {Element} [emptyEl] - Optional placeholder toggled when there are no tags.
 */
export function renderTagChips(container, tags, onRemove, emptyEl = null) {
    container.querySelectorAll('.tag-chip').forEach((chip) => chip.remove())
    emptyEl?.classList.toggle('d-none', tags.length > 0)
    for (const tag of tags) {
        const chip = document.createElement('span')
        chip.className =
            'badge rounded-pill ps-2 file-tag file-tag-active tag-chip'
        chip.append(tag)
        const removeBtn = document.createElement('button')
        removeBtn.type = 'button'
        removeBtn.className = 'btn p-0 mt-0 ms-1 remove-tag'
        removeBtn.ariaLabel = `Remove tag ${tag}`
        removeBtn.innerHTML = '<i class="fa-solid fa-xmark text-small"></i>'
        removeBtn.addEventListener('click', () => onRemove(tag))
        chip.append(removeBtn)
        container.append(chip)
    }
}

/**
 * Local chip-list editor: an input plus Add button manage an in-memory tag
 * list rendered as chips. Enter or comma in the input also adds.
 * @returns {{getTags: () => string[], reset: () => void}}
 */
export function initTagChipEditor({
    container,
    input,
    addBtn,
    emptyEl = null,
    onChange = null,
}) {
    let tags = []

    function render() {
        renderTagChips(container, tags, remove, emptyEl)
        onChange?.(tags)
    }

    function add() {
        const tag = input.value.trim().replaceAll(',', '')
        input.value = ''
        if (!tag || tags.includes(tag)) return
        tags.push(tag)
        render()
    }

    function remove(tag) {
        tags = tags.filter((existing) => existing !== tag)
        render()
    }

    addBtn?.addEventListener('click', add)
    input?.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ',') {
            event.preventDefault()
            add()
        }
    })

    return {
        getTags: () => [...tags],
        reset: () => {
            tags = []
            input.value = ''
            render()
        },
    }
}

/**
 * Wire the shared #bulk-tags-modal to a websocket bulk-edit method
 * (bulk_edit_file_tags or bulk_edit_album_tags).
 * @returns {{open: (pks: number[]) => void} | null} null when the modal is not on the page.
 */
export function initBulkTagsModal(socket, method, entity) {
    const modalEl = document.getElementById('bulk-tags-modal')
    if (!modalEl) return null
    let pks = []
    const editor = initTagChipEditor({
        container: modalEl.querySelector('#bulk-tags-container'),
        input: modalEl.querySelector('#bulk-tags-input'),
        addBtn: modalEl.querySelector('#bulk-tags-add-chip'),
        emptyEl: modalEl.querySelector('#bulk-tags-empty'),
    })

    function send(action) {
        const tags = editor.getTags()
        if (!tags.length || !pks.length) return
        socket.send(JSON.stringify({ method, pks, tags, action }))
        bootstrap.Modal.getOrCreateInstance(modalEl).hide()
    }

    modalEl
        .querySelector('#bulk-tags-apply-add')
        .addEventListener('click', () => send('add'))
    modalEl
        .querySelector('#bulk-tags-apply-remove')
        .addEventListener('click', () => send('remove'))

    return {
        open(selected) {
            pks = selected
            editor.reset()
            const s = pks.length === 1 ? '' : 's'
            modalEl.querySelector('#bulk-tags-label').textContent =
                `Tags — ${pks.length} ${entity}${s}`
            bootstrap.Modal.getOrCreateInstance(modalEl).show()
        },
    }
}
