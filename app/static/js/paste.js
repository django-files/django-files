// JS for Text Paste

$('#send-paste').on('submit', function (event) {
    event.preventDefault()
    console.log('#send-paste submit', event)
    const formData = new FormData(this)
    const text = formData.get('text')
    const file = new Blob([text], { type: 'text/plain' })
    formData.delete('text')
    let name = formData.get('name').toString() || 'paste.txt'
    name = name.includes('.') ? name : `${name}.txt`
    console.log(`name: ${name}`)
    formData.append('file', file, name)
    const form = $(this)
    $.ajax({
        type: form.attr('method'),
        url: form.attr('action'),
        data: formData,
        headers: { 'X-CSRFToken': csrftoken },
        success: function (data) {
            console.log('data:', data)
            form.trigger('reset')
        },
        error: function (jqXHR) {
            if (jqXHR.status === 400) {
                const message = `${jqXHR.status}: ${jqXHR.responseJSON.error}`
                show_toast(message, 'danger', '6000')
            } else {
                const message = `${jqXHR.status}: ${jqXHR.statusText}`
                show_toast(message, 'danger', '6000')
            }
        },
        cache: false,
        contentType: false,
        processData: false,
    })
})
