$(document).ready(function () {

    // Reload page on browser back/forward if new results
    let perfEntries = performance.getEntriesByType('navigation');
    if (perfEntries[0].type === 'back_forward') {
        let reloadSession = localStorage.getItem('reloadSession');
        if (reloadSession === 'true') {
            localStorage.removeItem('reloadSession');
            location.reload();
        }
    }

    // Monitor websockets for new data and update results
    const socket = new WebSocket('wss://' + window.location.host + '/ws/home/');
    console.log('Websockets Connected.');
    socket.onmessage = function (event) {
        let data = JSON.parse(event.data);
        $.get('/ajax/tdata/' + data.pk, function (response) {
            $('#results tbody').prepend(response);
            localStorage.setItem('reloadSession', 'true');
            let message = 'New Test Result: ' + data.pk;
            show_toast(message, 'success', '10000');
            console.log('Table Updated: ' + data.pk);
        });
    };

    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    // Generate Short URLs BUTTON
    // $('#create-short-btn').click(function () {
    $('#quick-short-form').on('submit', function (event) {
        let data = {url: $("#long-url").val()};
        event.preventDefault();
        // if (!data) {
        //     alert('Missing URL');
        // }
        $.ajax({
            // url: $('#create-short-btn').attr('data-target-url'),
            url: $('#quick-short-form').attr('action'),
            type: 'POST',
            headers: {'X-CSRFToken': csrftoken},
            // data: JSON.stringify(data),
            data: JSON.stringify(data),
            beforeSend: function (jqXHR) {
                //
            },
            success: function (data, textStatus, jqXHR) {
                console.log('Status: ' + jqXHR.status + ', Data: ' + JSON.stringify(data));
                alert('Short Created: ' + data['url']);
                location.reload();
            },
            complete: function (data, textStatus) {
                //
            },
            error: function (data, status, error) {
                console.log('Status: ' + data.status + ', Response: ' + data.responseText);
                // alert(data.responseText);
                let message = data.status + ': ' + data.responseJSON['error']
                show_toast(message, 'danger', '6000');
            },
            cache: false,
            contentType: false,
            processData: false
        });
    });

});
