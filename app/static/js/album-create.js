// Handles #albumsForm submit anywhere the create-album-modal is rendered.
// Dispatches an `album:created` CustomEvent on document so list views can refresh.

import { initTagChipEditor } from './tag-chips.js'

const _createAlbumModalEl = document.getElementById('create-album-modal')

const _tagsContainer = document.getElementById('create-album-tags')
const _tagsField = document.getElementById('album-tags')

// Chip editor with the preview-style "+" adder; the hidden field carries the
// list to the create endpoint as a comma-separated string.
const updateAlbumTagsField = (tags) => {
    _tagsField.value = tags.join(',')
}

const _tagEditor = _tagsContainer
    ? initTagChipEditor({
          container: _tagsContainer,
          onChange: updateAlbumTagsField,
      })
    : null

$('#albumsForm').on('submit', function (event) {
    event.preventDefault()
    const form = $(this)
    submitJsonForm(form, function (resp) {
        form.trigger('reset')
        _tagEditor?.reset()
        if (_createAlbumModalEl) {
            bootstrap.Modal.getOrCreateInstance(_createAlbumModalEl).hide()
        }
        document.dispatchEvent(
            new CustomEvent('album:created', { detail: resp })
        )
    })
})
