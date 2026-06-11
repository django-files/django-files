// JS for Authenticated Users

const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

$('.log-out').on('click', function (event) {
    // console.log('.log-out click', event)
    event.preventDefault()
    $('#log-out').trigger('submit')
})

$('#flush-cache').on('click', function (event) {
    event.preventDefault()
    $.ajax({
        type: 'POST',
        url: '/flush-cache/',
        headers: { 'X-CSRFToken': csrftoken },
        success: function () {
            show_toast('Cache flush queued.', 'info')
        },
        error: messageErrorHandler,
        cache: false,
        contentType: false,
        processData: false,
    })
})
