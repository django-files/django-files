// JS for Home Page

// Generate Short URLs BUTTON
$('#quick-short-form').on('submit', function (event) {
    let data = { url: $('#long-url').val() }
    event.preventDefault()
    $.ajax({
        url: $('#quick-short-form').attr('action'),
        type: 'POST',
        data: JSON.stringify(data),
        headers: { 'X-CSRFToken': csrftoken },
        success: function (data) {
            console.log('data: ' + data)
            alert('Short Created: ' + data['url'])
            location.reload()
        },
        error: function (jqXHR) {
            console.log('jqXHR.status: ' + jqXHR.status)
            console.log('jqXHR.statusText: ' + jqXHR.statusText)
            if (jqXHR.status === 400) {
                let data = jqXHR.responseJSON
                console.log(data)
                let message = jqXHR.status + ': ' + data['error']
                show_toast(message, 'danger', '6000')
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
