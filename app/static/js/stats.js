$(document).ready(function () {
    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

    // Handle update stats click
    $('#updateStatsBtn').click(function () {
        $.ajax({
            url: $('#updateStatsBtn').attr('data-target-url'),
            type: 'POST',
            headers: { 'X-CSRFToken': csrftoken },
            success: function (data) {
                console.log('data: ' + JSON.stringify(data))
                alert('Stats Update Submitted. Page will now Reload...')
                location.reload()
            },
            error: function (jqXHR) {
                console.log('jqXHR.status: ' + jqXHR.status)
                console.log('jqXHR.statusText: ' + jqXHR.statusText)
                let message = jqXHR.status + ': ' + jqXHR.statusText
                show_toast(message, 'danger', '6000')
            },
            cache: false,
            contentType: false,
            processData: false,
        })
    })
})
