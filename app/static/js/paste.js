$(document).ready(function () {
    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

    // Handle paste submissions
    $('#send-paste').submit(function (event) {
        event.preventDefault()
        console.log('#send-paste.submit')
        let formData = new FormData(this)
        const text = formData.get('text')
        const file = new Blob([text], { type: 'text/plain' })
        formData.delete('text')
        const name = formData.get('name') || 'paste.txt'
        console.log(name)
        formData.append('file', file, name)

        $.ajax({
            type: $(this).attr('method'),
            url: $(this).attr('action'),
            data: formData,
            headers: { 'X-CSRFToken': csrftoken },
            success: function (data) {
                console.log('JSON data: ' + JSON.stringify(data))
                $(this).trigger('reset')
            },
            error: function (jqXHR) {
                console.log('jqXHR.status: ' + jqXHR.status)
                console.log('jqXHR.statusText: ' + jqXHR.statusText)
                if (jqXHR.status === 400) {
                    console.log(jqXHR.responseJSON)
                    show_toast(jqXHR.responseJSON['error'], 'danger', '6000')
                } else {
                    let message = jqXHR.status + ': ' + jqXHR.statusText
                    show_toast(message, 'danger', '6000')
                }
            },
            cache: false,
            contentType: false,
            processData: false,
        })
    })
})
