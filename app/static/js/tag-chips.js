// Shared tag-chip rendering and editing, used by the album Manage Tags
// modal, the create-album modal, and the bulk tags modal. Mirrors the file
// preview sidebar tag UI: chips plus a "+" chip that reveals an inline input.

/**
 * Render removable tag chips into a container. Chips are inserted before the
 * "+" adder chip when one is present so it stays at the end, like the preview.
 * @param {Element} container - Chip parent; existing .tag-chip children are replaced.
 * @param {string[]} tags - Tag names to render.
 * @param {(tag: string) => void} onRemove - Called with the tag when its X is clicked.
 */
export function renderTagChips(container, tags, onRemove) {
    container.querySelectorAll('.tag-chip').forEach((chip) => chip.remove())
    const adder = container.querySelector('.addto-tag-group')
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
        if (adder) adder.before(chip)
        else container.append(chip)
    }
}

/**
 * Append the preview-style "+" adder chip: clicking it reveals an inline
 * input; Enter submits via onAdd, Escape cancels, blurring while empty hides.
 * @returns {{reset: () => void}}
 */
export function createTagAdder(container, onAdd) {
    const group = document.createElement('span')
    group.className = 'badge rounded-pill file-tag addto-tag-group'
    group.innerHTML = `
        <button type="button" class="btn p-0 addto-tag"><i class="fa-solid fa-plus"></i></button>
        <span class="tag-add-container d-none">
            <input class="tag-search-input" autocomplete="off"
                   placeholder="Add tag…" aria-label="Add tag" maxlength="255">
        </span>`
    container.append(group)

    const addBtn = group.querySelector('.addto-tag')
    const addContainer = group.querySelector('.tag-add-container')
    const input = group.querySelector('.tag-search-input')

    function hideInput() {
        addContainer.classList.add('d-none')
    }

    function closeInput() {
        input.value = ''
        hideInput()
    }

    function submitTag() {
        const tag = input.value.trim().replaceAll(',', '')
        if (!tag) return
        onAdd(tag)
        closeInput()
    }

    addBtn.addEventListener('click', () => {
        addContainer.classList.remove('d-none')
        input.focus()
    })
    input.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault()
            submitTag()
        } else if (event.key === 'Escape') {
            closeInput()
        }
    })
    input.addEventListener('blur', () => {
        if (!input.value.trim()) setTimeout(hideInput, 150)
    })

    return { reset: closeInput }
}

/**
 * Local chip-list editor: the "+" adder manages an in-memory tag list
 * rendered as chips, no server round-trip.
 * @returns {{getTags: () => string[], reset: () => void}}
 */
export function initTagChipEditor({ container, onChange = null }) {
    let tags = []

    function render() {
        renderTagChips(container, tags, remove)
        onChange?.(tags)
    }

    function remove(tag) {
        tags = tags.filter((existing) => existing !== tag)
        render()
    }

    const adder = createTagAdder(container, (tag) => {
        if (tags.includes(tag)) return
        tags.push(tag)
        render()
    })

    return {
        getTags: () => [...tags],
        reset: () => {
            tags = []
            adder.reset()
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
