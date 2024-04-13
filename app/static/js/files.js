// JS for Files

const filesTable = $('#files-table')

let filesDataTable
if (typeof DataTable !== 'undefined' && filesTable.length) {
    filesDataTable = filesTable.DataTable({
        order: [0, 'desc'],
        processing: true,
        saveState: true,
        pageLength: -1,
        lengthMenu: [
            [10, 25, 50, 100, 250, -1],
            [10, 25, 50, 100, 250, 'All'],
        ],
        columnDefs: [
            { targets: 2, type: 'file-size' },
            {
                targets: 4,
                render: DataTable.render.datetime('DD MMM YYYY, kk:mm'),
            },
            { targets: [6, 7, 9], orderable: false },
        ],
    })
}

socket?.addEventListener('message', function (event) {
    // console.log('socket.message: files.js:', event)
    if (!filesTable.length) {
        return console.log('filesTable not found in DOM')
    }
    let data = JSON.parse(event.data)
    if (data.event === 'file-new') {
        $.get(`/ajax/files/tdata/${data.pk}`, function (response) {
            if (filesDataTable) {
                filesDataTable.row.add($(response)).draw()
            } else {
                filesTable.find('tbody').prepend(response)
            }
            const row = $(`#file-${data.pk}`)
            row.find('.ctx-expire').on('click', cxtSetExpire)
            row.find('.ctx-private').on('click', ctxSetPrivate)
            row.find('.ctx-password').on('click', ctxSetPassword)
            row.find('.ctx-delete').on('click', ctxDeleteFile)
        })
    } else if (data.event === 'file-delete') {
        console.log(`File Deleted: ${data.pk}`)
        $(`#file-${data.pk}`).remove()
    }
})

$('#user').on('change', function (event) {
    let user = $(this).val()
    console.log(`user: ${user}`)
    if (user) {
        let url = new URL(location.href)
        url.searchParams.set('user', user)
        location.href = url.toString()
    }
})

const mediaOuter = document.getElementById('media-outer')
const mediaImage = document.getElementById('media-image')
const loadingImage = '/static/images/assets/loading.gif'

// let mediaWidth = parseInt(window.innerWidth * 0.5)
// mediaImage.style.maxWidth = `${mediaWidth}px`
mediaImage.style.maxWidth = '320px'

const virtualElement = {
    getBoundingClientRect: generateGetBoundingClientRect(),
}

const instance = Popper.createPopper(virtualElement, mediaOuter)

mediaImage.onload = function (event) {
    instance.update()
}

document.addEventListener('mousemove', ({ clientX: x, clientY: y }) => {
    virtualElement.getBoundingClientRect = generateGetBoundingClientRect(x, y)
    instance.update()
})

function generateGetBoundingClientRect(x = 0, y = 0) {
    return () => ({
        width: 0,
        height: 0,
        top: y + 23,
        right: x,
        bottom: y,
        left: x,
    })
}

document.querySelectorAll('tr[id*="file-"]').forEach((element) => {
    const el = element.querySelector('.file-link')
    el.addEventListener('mouseover', onMouseOver)
    el.addEventListener('mouseout', onMouseOut)
})

function onMouseOver(event) {
    console.debug('onMouseOver', event)
    instance.update()
    const tr = event.target.closest('tr')
    console.log('tr:', tr)
    console.log('url:', tr.dataset.rawUrl)
    const imageExtensions = /\.(gif|ico|jpeg|jpg|png|svg|webp)$/i
    if (tr.dataset.rawUrl.match(imageExtensions)) {
        mediaImage.src = loadingImage
        mediaImage.src = tr.dataset.rawUrl
        mediaOuter.classList.remove('d-none')
    } else {
        mediaOuter.classList.add('d-none')
        mediaImage.src = loadingImage
    }
}

function onMouseOut(event) {
    console.debug('onMouseOut', event)
    mediaOuter.classList.add('d-none')
    mediaImage.src = loadingImage
}
