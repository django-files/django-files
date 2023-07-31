$(document).ready(function() {

    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    // Init the logout form click function
    $('.log-out').on('click', function () {
        $('#log-out').submit();
        return false;
    });

    // Init the flush-cache click function
    $("#flush-cache").click(function () {
        console.log('flush-cache clicked...');
        $.ajax({
            type: 'POST',
            url: '/flush-cache/',
            headers: {'X-CSRFToken': csrftoken},
            beforeSend: function () {
                console.log('beforeSend');
            },
            success: function (response) {
                console.log('response: ' + response);
                alert('Cache Flush Successfully Sent...');
            },
            error: function (xhr, status, error) {
                console.log('xhr status: ' + xhr.status);
                console.log('status: ' + status);
                console.log('error: ' + error);
                alert('Error: ' + xhr.responseText)
            },
            complete: function () {
                console.log('complete');
                location.reload();
            }
        });
        return false;
    });

});
