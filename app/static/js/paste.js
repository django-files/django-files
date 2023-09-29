$(document).ready(function () {
    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

    // Handle paste submissions
    $('#send-paste').submit(function (event) {
        event.preventDefault()
        console.log('#send-paste.submit')
        const form = $(this)
        $.ajax({
            type: form.attr('method'),
            url: form.attr('action'),
            data: new FormData(this),
            headers: { 'X-CSRFToken': csrftoken },
            success: function (data) {
                console.log('data: ' + JSON.stringify(data))
                form.trigger('reset')
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
