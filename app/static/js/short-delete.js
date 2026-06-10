// Handles the delete-short modal lifecycle anywhere the modal is rendered.
// Listens for clicks on .delete-short-btn (delegated to document) and confirms
// via #short-delete-confirm. Dispatches a `short:deleted` CustomEvent with
// { id } on success so list views can remove the row.

const _deleteShortModalEl = document.getElementById('delete-short-modal')
const _deleteShortModal = _deleteShortModalEl
    ? bootstrap.Modal.getOrCreateInstance(_deleteShortModalEl)
    : null
let _pendingShortDeleteId = null

document.addEventListener('click', function (event) {
    const btn = event.target.closest('.delete-short-btn')
    if (!btn) return
    _pendingShortDeleteId = btn.dataset.hookId
    _deleteShortModal?.show()
})

document
    .getElementById('short-delete-confirm')
    ?.addEventListener('click', function () {
        const id = _pendingShortDeleteId
        if (!id) return
        $.ajax({
            type: 'POST',
            url: `/ajax/delete/short/${id}/`,
            headers: { 'X-CSRFToken': csrftoken },
            success: function () {
                _deleteShortModal?.hide()
                document.dispatchEvent(
                    new CustomEvent('short:deleted', { detail: { id } })
                )
                show_toast(`Short URL ${id} Successfully Removed.`, 'success')
            },
            error: function (jqXHR) {
                _deleteShortModal?.hide()
                messageErrorHandler(jqXHR)
            },
            cache: false,
            contentType: false,
            processData: false,
        })
    })
