// JS for Stats

$('#updateStatsBtn').on('click', function () {
    $.ajax({
        type: 'POST',
        url: $(this).attr('data-target-url'),
        headers: { 'X-CSRFToken': csrftoken },
        success: function (data) {
            console.log('data:', data)
            alert('Stats Update Submitted. Page will now Reload...')
            location.reload()
        },
        error: function (jqXHR) {
            let message = `${jqXHR.status}: ${jqXHR.statusText}`
            show_toast(message, 'danger', '6000')
        },
        cache: false,
        contentType: false,
        processData: false,
    })
})
