console.log('Connecting to WebSocket...')

let ws

const socket = connect()

function connect() {
    if (location.protocol == 'https:') {
        ws = new WebSocket('wss://' + window.location.host + '/ws/home/');
    } else {
        // TODO: guard against this happening outside of dev
        ws = new WebSocket('ws://' + window.location.host + '/ws/home/');
    }
    // ws.onopen = function() {
    //   // subscribe to some channels
    //   ws.send(JSON.stringify({
    //       //.... some message the I must send when I connect ....
    //   }));
    // };
  
    ws.onmessage = function(e) {
      console.log('Message:', e.data);
    };
  
    ws.onclose = function(e) {
      console.log('Socket is closed. Reconnect will be attempted in 1 second.', e.reason);
      setTimeout(function() {
        connect();
      }, 1000);
    };
  
    ws.onerror = function(err) {
      console.error('Socket encountered error: ', err.message, 'Closing socket');
      ws.close();
    };

    return ws
  }
