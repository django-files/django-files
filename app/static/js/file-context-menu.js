import { socket } from './socket.js'

// JS for Context Menu

console.debug('LOADING: file-context-menu.js')

const fileExpireModal = $('#fileExpireModal')
const filePasswordModal = $('#filePasswordModal')
const fileDeleteModal = $('#fileDeleteModal')
const fileRenameModal = $('#fileRenameModal')

// these listeners are only used on preview page
// see file-table for file table ctx menu listeners
$('.ctx-expire').on('click', ctxSetExpire)
$('.ctx-private').on('click', ctxSetPrivate)
$('.ctx-password').on('click', ctxSetPassword)
$('.ctx-delete').on('click', ctxDeleteFile)
$('.ctx-rename').on('click', ctxRenameFile)

// Expire Form

fileExpireModal.on('shown.bs.modal', function (event) {
    console.log('fileExpireModal shown.bs.modal:', event)
    $(this).find('input').trigger('focus').trigger('select')
})

$('#modal-expire-form').on('submit', function (event) {
    console.log('#modal-expire-form submit:', event)
    event.preventDefault()
    const data = genData($(this), 'set-expr-file')
    console.log('data:', data)
    socket.send(JSON.stringify(data))
    fileExpireModal.modal('hide')
    $(`#ctx-menu-${data.pk} input[name=current-file-expiration]`).val(data.expr)
})

// Password Form
// TODO: Cleanup Password Forms

filePasswordModal.on('shown.bs.modal', function (event) {
    console.log('filePasswordModal shown.bs.modal:', event)
    $(this).find('input').trigger('focus').trigger('select')
})

$('#modal-password-form').on('submit', function (event) {
    console.log('#modal-password-form submit:', event)
    event.preventDefault()
    const data = genData($(this), 'set-password-file')
    console.log('data:', data)
    socket.send(JSON.stringify(data))
    $(`#ctx-menu-${data.pk} input[name=current-file-password]`).val(
        data.password
    )
    filePasswordModal.modal('hide')
})

$('#password-unmask').on('click', function (event) {
    console.log('#password-unmask click:', event)
    const input = $('#password')
    const type = input.attr('type') === 'password' ? 'text' : 'password'
    input.prop('type', type)
})

$('#password-copy').on('click', async function (event) {
    console.log('#password-copy click:', event)
    await navigator.clipboard.writeText($('#password').val())
    show_toast('Password copied!', 'info')
})

$('#password-generate').on('click', async function (event) {
    console.log('#password-generate click:', event)
    const password = genRand(12)
    $('#password').val(password)
    await navigator.clipboard.writeText(password)
    show_toast('Password generated and copied!', 'info')
})

// Delete File Form

$('#confirm-delete').on('click', function (event) {
    // TODO: Handle IF/ELSE Better
    const pk = $(this).data('pk')
    console.log(`#confirm-delete click pk: ${pk}`, event)
    socket.send(JSON.stringify({ method: 'delete-file', pk: pk }))
    if (window.location.pathname.startsWith('/u/')) {
        window.location.replace('/files')
    } else {
        fileDeleteModal.modal('hide')
    }
})

// Rename Form

fileRenameModal.on('shown.bs.modal', function (event) {
    console.log('fileRenameModal shown.bs.modal:', event)
    $(this).find('input').trigger('focus').trigger('select')
    let name = fileRenameModal.find('input[name=name]').val()
    let ext = name.split('.').pop()
    console.log(0, name.length - (ext.length + 1))
    fileRenameModal.find('input[name=name]')[0].setSelectionRange(0, name.length - (ext.length + 1))
})

$('#modal-rename-form').on('submit', function (event) {
    console.log('#modal-rename-form submit:', event)
    event.preventDefault()
    const data = genData($(this), 'set-file-name')
    console.log('data:', data)
    socket.send(JSON.stringify(data))
    fileRenameModal.modal('hide')
    $(`#ctx-menu-${data.pk} input[name=current-file-expiration]`).val(data.name)
})

// Event Listeners

export function ctxSetExpire(event) {
    const pk = getPrimaryKey(event)
    console.log(`getPrimaryKey pk: ${pk}`, event)
    fileExpireModal.find('input[name=pk]').val(pk)
    const expire = $(`#ctx-menu-${pk} input[name=current-file-expiration]`)
    console.log(`expire: ${expire}`)
    const expireValue = expire === 'Never' ? '' : expire.val().toString().trim()
    console.log(`expireInput: ${expireValue}`)
    $('#expr').val(expireValue)
    fileExpireModal.modal('show')
}

export function ctxSetPrivate(event) {
    const pk = getPrimaryKey(event)
    console.log(`ctxSetPrivate pk: ${pk}`, event)
    socket.send(JSON.stringify({ method: 'toggle-private-file', pk: pk }))
}

export function ctxSetPassword(event) {
    const pk = getPrimaryKey(event)
    console.log(`ctxSetPassword pk: ${pk}`, event)
    filePasswordModal.find('input[name=pk]').val(pk)
    const input = $(`#ctx-menu-${pk} input[name=current-file-password]`)
    // console.log('input:', input)
    const password = input.val().toString().trim()
    console.log(`password: ${password}`)
    // $('#password').val(input.val())
    filePasswordModal.find('input[name=password]').val(password)
    filePasswordModal.modal('show')
}

export function ctxDeleteFile(event) {
    const pk = getPrimaryKey(event)
    console.log(`ctxDeleteFile pk: ${pk}`, event)
    $('#confirm-delete').data('pk', pk)
    fileDeleteModal.modal('show')
}

export function ctxRenameFile(event) {
    const pk = getPrimaryKey(event)
    console.log(`ctxRenameFile pk: ${pk}`, event)
    fileRenameModal.find('input[name=pk]').val(pk)
    const input = $(`#ctx-menu-${pk} input[name=current-file-name]`)
    const name = input.val().toString().trim()
    fileRenameModal.find('input[name=name]').val(name)
    fileRenameModal.modal('show')
}

function getPrimaryKey(event) {
    const menu = event.target.closest('div')
    let pk = menu?.dataset?.id
    if (!pk) {
        console.warn('OLD PK QUERY USED')
        pk = $(this).parent().parent().parent().data('pk')
    }
    return pk
}

/**
 * Generate Random String at length
 * @param {Number} length
 * @return {String}
 */
function genRand(length) {
    const chars =
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    let result = ''
    let counter = 0
    while (counter < length) {
        const rand = Math.floor(Math.random() * chars.length)
        result += chars.charAt(rand)
        counter += 1
    }
    return result
}

/**
 * Convert Form Object to Object
 * @param {jQuery} form $(this) from on submit event
 * @param {String} method The method key value
 * @return {Object}
 */
function genData(form, method) {
    const data = { method: method }
    for (const element of form.serializeArray()) {
        data[element['name']] = element['value']
    }
    return data
}

//////// Socket Event Handlers ////////////
// this is where event handlers SPECIFIC to the context menu go

function messageFileRename(data) {
    console.log($(`#ctx-menu-${data.id} input[name=current-file-name]`))
    $(`#ctx-menu-${data.id} input[name=current-file-name]`).val(data.name)
}


socket?.addEventListener('message', function (event) {
    let data = JSON.parse(event.data)
    console.log(event)
    if (data.event === 'set-file-name') {
        messageFileRename(data)
    }
})
