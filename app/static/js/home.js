// JS for Home Page

$('#quick-short-form').on('submit', function (event) {
    console.log('#quick-short-form submit', event)
    event.preventDefault()
    const data = { url: $('#long-url').val() }
    $.ajax({
        type: 'POST',
        url: $(this).attr('action'),
        data: JSON.stringify(data),
        headers: { 'X-CSRFToken': csrftoken },
        success: function (data) {
            console.log('data:', data)
            alert(`Short Created: ${data.url}`)
            location.reload()
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
