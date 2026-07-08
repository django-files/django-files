/**
 * Wires the tag add/remove UI in the file preview sidebar.
 * Returns a handleTagUpdate(data) callback for the WebSocket handler.
 */
export function initTagSelector(container, socket) {
    const tagContainer = container.querySelector(
        '.tag-container[id^="tags-file-"]'
    )
    if (!tagContainer) return null

    const filePk = tagContainer.id.replace('tags-file-', '')

    function removeTagPress(event) {
        const tag = event.target.closest('button').dataset.tag
        socket.send(
            JSON.stringify({
                method: 'remove_file_tag',
                pk: filePk,
                tag,
            })
        )
    }

    container
        .querySelectorAll('.remove-tag')
        .forEach((el) => el.addEventListener('click', removeTagPress))

    const addToTagButton = container.querySelector('.addto-tag')
    const addTagInput = container.querySelector('.tag-search-input')
    const addTagContainer = container.querySelector('.tag-add-container')

    function hideInput() {
        addTagContainer.classList.add('d-none')
    }

    function closeInput() {
        addTagInput.value = ''
        hideInput()
    }

    function submitTag() {
        const tag = addTagInput.value.trim()
        if (!tag) return
        socket.send(
            JSON.stringify({
                method: 'add_file_tag',
                pk: filePk,
                tag,
            })
        )
        closeInput()
    }

    addToTagButton?.addEventListener('click', () => {
        addTagContainer.classList.remove('d-none')
        addTagInput.focus()
    })

    addTagInput?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault()
            submitTag()
        } else if (e.key === 'Escape') {
            closeInput()
        }
    })

    addTagInput?.addEventListener('blur', () => {
        if (!addTagInput.value.trim()) setTimeout(hideInput, 150)
    })

    function handleTagUpdate(data) {
        if (data.removed) {
            for (const tag of data.removed) {
                tagContainer
                    .querySelector(
                        `[data-tag="${CSS.escape(tag)}"].file-tag-active`
                    )
                    ?.remove()
            }
        }
        if (data.added) {
            const addGroup = tagContainer.querySelector('.addto-tag-group')
            for (const tag of data.added) {
                if (
                    tagContainer.querySelector(
                        `[data-tag="${CSS.escape(tag)}"].file-tag-active`
                    )
                )
                    continue
                const span = document.createElement('span')
                span.className =
                    'badge rounded-pill ps-2 file-tag file-tag-active'
                span.dataset.tag = tag
                span.innerHTML = `${tag} <button class="btn p-0 mt-0 ms-1 remove-tag" data-tag="${tag}"><i class="fa-solid fa-xmark text-small"></i></button>`
                span.querySelector('.remove-tag').addEventListener(
                    'click',
                    removeTagPress
                )
                addGroup.before(span)
            }
        }
    }

    return handleTagUpdate
}
