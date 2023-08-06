$(document).ready(function() {

    // Get and set the csrf_token
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    // Generate Short URLs
    $('#create-short-btn').click(function () {
        let data= { url: $("#long-url").val()};
        $.ajax({
            url: $('#create-short-btn').attr('data-target-url'),
            type: 'POST',
            headers: {'X-CSRFToken': csrftoken},
            data: JSON.stringify(data),
            beforeSend: function( jqXHR ){
                //
            },
            success: function(data, textStatus, jqXHR){
                console.log('Status: '+jqXHR.status+', Data: '+JSON.stringify(data));
                alert('Stats Update Submitted. Page will now Reload...');
            },
            complete: function(data, textStatus ){
                console.log(data.responseJSON['url']);
                location.reload();
            },
            error: function (data, status, error) {
                console.log('Status: '+data.status+', Response: '+data.responseText);
                alert(data.responseText)
            },
            cache: false,
            contentType: false,
            processData: false
        });
    });

});
