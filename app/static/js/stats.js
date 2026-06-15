// JS for Stats

$(document).on('click', '.updateStatsBtn', function () {
    $.ajax({
        type: 'POST',
        url: $(this).attr('data-target-url'),
        headers: { 'X-CSRFToken': csrftoken },
        success: function () {
            show_toast('Stats processing queued.', 'info')
            document.dispatchEvent(new CustomEvent('stats:reload'))
        },
        error: messageErrorHandler,
        cache: false,
        contentType: false,
        processData: false,
    })
})
