// JS for Text Paste

$('#send-paste').on('submit', function (event) {
    event.preventDefault()
    console.log('#send-paste submit', event)
    const formData = new FormData(this)
    const text = formData.get('text')
    if (!text) {
        show_toast('Text is Empty.', 'danger')
        return
    }
    const file = new Blob([text], { type: 'text/plain' })
    formData.delete('text')
    let name = formData.get('name').toString() || 'paste.txt'
    name = name.includes('.') ? name : `${name}.txt`
    console.log(`name: ${name}`)
    formData.append('file', file, name)
    const form = $(this)
    console.log('form:', form)
    $.ajax({
        type: form.attr('method'),
        url: form.attr('action'),
        data: formData,
        headers: { 'X-CSRFToken': csrftoken },
        success: function (data) {
            console.log('data:', data)
            form.trigger('reset')
            const link = $('<span>Text Uploaded: </span>').append(
                $('<a>', {
                    href: data.url,
                    text: data.name,
                    class: 'link-light',
                    target: '_blank',
                    rel: 'noopener',
                })
            )
            show_toast(link, 'success')
        },
        error: messageErrorHandler,
        cache: false,
        contentType: false,
        processData: false,
    })
})
