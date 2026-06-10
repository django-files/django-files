// Handles #shortsForm submit anywhere the create-short-modal is rendered.
// Dispatches a `short:created` CustomEvent on document so list views can refresh.

const _createShortModalEl = document.getElementById('create-short-modal')

$('#shortsForm').on('submit', function (event) {
    event.preventDefault()
    const form = $(this)
    submitJsonForm(form, function (resp) {
        form.trigger('reset')
        if (_createShortModalEl) {
            bootstrap.Modal.getOrCreateInstance(_createShortModalEl).hide()
        }
        show_toast(`Short Created: ${resp.url}`, 'success')
        document.dispatchEvent(
            new CustomEvent('short:created', { detail: resp })
        )
    })
})
