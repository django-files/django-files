// Shared tag-chip rendering and editing, used by the album Manage Tags
// modal, the create-album modal, and the bulk tags modal. Mirrors the file
// preview sidebar tag UI: chips plus a "+" chip that reveals an inline input.

/**
 * Render removable tag chips into a container. Chips are inserted before the
 * "+" adder chip when one is present so it stays at the end, like the preview.
 * @param {Element} container - Chip parent; existing .tag-chip children are replaced.
 * @param {(string | {tag: string, label: string})[]} tags - Tag names, or
 *        objects when the displayed label differs (e.g. bulk "(n)" counts).
 * @param {(tag: string) => void} onRemove - Called with the tag when its X is clicked.
 */
export function renderTagChips(container, tags, onRemove) {
    container.querySelectorAll('.tag-chip').forEach((chip) => chip.remove())
    const adder = container.querySelector('.addto-tag-group')
    for (const item of tags) {
        const tag = typeof item === 'string' ? item : item.tag
        const label = typeof item === 'string' ? item : item.label
        const chip = document.createElement('span')
        chip.className =
            'badge rounded-pill ps-2 file-tag file-tag-active tag-chip'
        chip.append(label)
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
 * (bulk_edit_file_tags or bulk_edit_album_tags). Mirrors the bulk album
 * manager: the union of tags across the selection renders as chips, with a
 * "(n)" count on tags only n of N selected items carry. Removing a chip or
 * adding via the "+" chip applies to the whole selection immediately.
 * @returns {{open: (items: {pk: number, tags: string[]}[]) => void} | null}
 *          null when the modal is not on the page.
 */
export function initBulkTagsModal(socket, method, entity) {
    const modalEl = document.getElementById('bulk-tags-modal')
    if (!modalEl) return null
    const container = modalEl.querySelector('#bulk-tags-container')
    let pks = []
    let total = 0
    const counts = new Map()

    function send(tag, action) {
        socket.send(JSON.stringify({ method, pks, tags: [tag], action }))
    }

    function render() {
        const chips = [...counts.entries()]
            .sort((a, b) => a[0].localeCompare(b[0]))
            .map(([tag, count]) => ({
                tag,
                label: count < total ? `${tag} (${count})` : tag,
            }))
        renderTagChips(container, chips, (tag) => {
            send(tag, 'remove')
            counts.delete(tag)
            render()
        })
    }

    const adder = createTagAdder(container, (tag) => {
        send(tag, 'add')
        // reuse an existing chip's casing so the optimistic count lands on it
        const existing = [...counts.keys()].find(
            (name) => name.toLowerCase() === tag.toLowerCase()
        )
        counts.set(existing ?? tag, total)
        render()
    })

    return {
        open(items) {
            pks = items.map((item) => item.pk)
            total = items.length
            counts.clear()
            for (const item of items) {
                for (const tag of item.tags || []) {
                    counts.set(tag, (counts.get(tag) || 0) + 1)
                }
            }
            adder.reset()
            render()
            const s = total === 1 ? '' : 's'
            modalEl.querySelector('#bulk-tags-label').textContent =
                `Tags — ${total} ${entity}${s}`
            bootstrap.Modal.getOrCreateInstance(modalEl).show()
        },
    }
}
