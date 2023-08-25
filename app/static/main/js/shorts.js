$(document).ready(function () {
    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value

    // Handle Shorts FORM Submit
    $('#shorts-form').on('submit', function (event) {
        event.preventDefault()
        let data = new FormData($(this)[0])

        data.forEach((value, key) => (data[key] = value))
        // let json = JSON.stringify(formData);

        $.ajax({
            // url: window.location.pathname,
            url: $('#shorts-form').attr('action'),
            type: 'POST',
            headers: { 'X-CSRFToken': csrftoken },
            // data: formData,
            data: JSON.stringify(data),
            beforeSend: function (jqXHR) {
                //
            },
            success: function (data, textStatus, jqXHR) {
                console.log(
                    'Status: ' +
                        jqXHR.status +
                        ', Data: ' +
                        JSON.stringify(data)
                )
                alert('Short Created: ' + data['url'])
                location.reload()
                // let message = 'Short Created: ' + data['url'];
                // show_toast(message,'success', '6000');
            },
            complete: function (data, textStatus) {
                //
            },
            error: function (data, status, error) {
                console.log(
                    'Status: ' +
                        data.status +
                        ', Response: ' +
                        data.responseText
                )
                // TODO: Replace this with real error handling
                let message = data.status + ': ' + data.responseJSON['error']
                show_toast(message, 'danger', '6000')
            },
            cache: false,
            contentType: false,
            processData: false,
        })
    })
})
