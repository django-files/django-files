$(document).ready(function () {

    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    // Handle update stats click
    $('#update-stats-btn').click(function () {
        $.ajax({
            url: $('#update-stats-btn').attr('data-target-url'),
            type: 'POST',
            headers: {'X-CSRFToken': csrftoken},
            beforeSend: function (jqXHR) {
                //
            },
            success: function (data, textStatus, jqXHR) {
                console.log('Status: ' + jqXHR.status + ', Data: ' + JSON.stringify(data));
                alert('Stats Update Submitted. Page will now Reload...');
            },
            complete: function (data, textStatus) {
                console.log(data);
                location.reload();
            },
            error: function (data, status, error) {
                console.log('Status: ' + data.status + ', Response: ' + data.responseText);
                alert(data.responseText)
            },
            cache: false,
            contentType: false,
            processData: false
        });
    });

});
