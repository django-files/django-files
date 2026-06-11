// Handles #albumsForm submit anywhere the create-album-modal is rendered.
// Dispatches an `album:created` CustomEvent on document so list views can refresh.

const _createAlbumModalEl = document.getElementById('create-album-modal')

$('#albumsForm').on('submit', function (event) {
    event.preventDefault()
    const form = $(this)
    submitJsonForm(form, function (resp) {
        form.trigger('reset')
        if (_createAlbumModalEl) {
            bootstrap.Modal.getOrCreateInstance(_createAlbumModalEl).hide()
        }
        document.dispatchEvent(
            new CustomEvent('album:created', { detail: resp })
        )
    })
})
