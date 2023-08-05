$(document).ready(function() {

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
    socket.onmessage = function(event) {
        let data = JSON.parse(event.data);
        $.get('/ajax/tdata/' + data.pk, function(response) {
            $('#results tbody').prepend(response);
            localStorage.setItem('reloadSession', 'true');
            let message = 'New Test Result: ' + data.pk;
            show_toast(message,'success', '10000');
            console.log('Table Updated: ' + data.pk);
        });
    };

    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    // Define Hook Modal and Delete handlers
    const deleteHookModal = new bootstrap.Modal('#delete-file-modal', {});
    let hookID;
    $('.delete-file-btn').click(function () {
        hookID = $(this).data('hook-id');
        console.log(hookID);
        deleteHookModal.show();
    });
    $('#confirm-delete-hook-btn').click(function () {
        if ($('#confirm-delete-hook-btn').hasClass('disabled')) { return; }
        console.log(hookID);
        $.ajax({
            type: 'POST',
            url: `/ajax/delete/file/${hookID}/`,
            headers: {'X-CSRFToken': csrftoken},
            beforeSend: function () {
                console.log('beforeSend');
                $('#confirm-delete-hook-btn').addClass('disabled');
            },
            success: function (response) {
                console.log('response: ' + response);
                deleteHookModal.hide();
                console.log('removing #file-' + hookID);
                let count = $('#files-table tr').length;
                $('#file-' +hookID).remove();
                if (count<=2) {
                    console.log('removing #files-table@ #files-table');
                    $('#files-table').remove();
                }
                let message = 'File ' + hookID + ' Successfully Removed.';
                show_toast(message,'success');
            },
            error: function (xhr, status, error) {
                console.log('xhr status: ' + xhr.status);
                console.log('status: ' + status);
                console.log('error: ' + error);
                deleteHookModal.hide();
                let message = xhr.status + ': ' + error
                show_toast(message,'danger', '15000');
            },
            complete: function () {
                console.log('complete');
                $('#confirm-delete-hook-btn').removeClass('disabled');
            }
        });
    });

    // Handle profile save button click and response
    $('#update-stats-btn').click(function () {
        console.log('CLICKY CLICKY');
        if ($('#update-stats-btn').hasClass('disabled')) { return; }
        $.ajax({
            // url: window.location.pathname,
            url: $('#update-stats-btn').attr('data-target-url'),
            type: 'POST',
            headers: {'X-CSRFToken': csrftoken},
            beforeSend: function( jqXHR ){
                $('#update-stats-btn').addClass('disabled');
                console.log('url: ' + $('#update-stats-btn').attr('data-target-url'));
            },
            success: function(data, textStatus, jqXHR){
                console.log('Status: '+jqXHR.status+', Data: '+JSON.stringify(data));
                alert('Stats Update Submitted. Page will now Reload...');
            },
            complete: function(data, textStatus ){
                $('#update-stats-btn').removeClass('disabled');
                console.log(data);
                location.reload();
            },
            error: function (data, status, error) {
                console.log('Status: '+data.status+', Response: '+data.responseText);
                // let message = data.status + ': ' + error
                // show_toast(message,'danger', '6000');
                alert(data.responseText)
            },
            cache: false,
            contentType: false,
            processData: false
        });
    });

});
