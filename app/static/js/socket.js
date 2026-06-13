// JS for Web Sockets
// TODO: Look Into Moving Everything Here for Auto Reconnect

let disconnected = false
export let socket //NOSONAR
let heartbeatInterval
const _initializedSockets = new WeakSet()

console.log('Connecting to WebSocket...')
wsConnect()

async function wsConnect() {
    if (socket) {
        console.warn('Closing Existing WebSocket Connection!')
        socket.close()
    }
    const toast = bootstrap.Toast.getOrCreateInstance($('#disconnected-toast'))
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    socket = new WebSocket(`${protocol}//${window.location.host}/ws/home/`)
    socket.onopen = function (event) {
        console.log('WebSocket Connected.', event)
        disconnected = false
        clearInterval(heartbeatInterval)
        heartbeatInterval = setInterval(() => {
            if (socket.readyState === WebSocket.OPEN) {
                socket.send('ping')
            }
        }, 30 * 1000)
        if (toast.isShown()) {
            $('#disconnected-toast-title')
                .removeClass('text-danger')
                .addClass('text-warning')
                .text('Connected')
            toast.hide()
        }
        document.dispatchEvent(new CustomEvent('wsConnected'))
    }
    // socket.onmessage = function (event) {
    //     console.log('socket.onmessage:', event)
    // }
    socket.onclose = function (event) {
        clearInterval(heartbeatInterval)
        if (![1000, 1001].includes(event.code)) {
            if (!disconnected) {
                console.warn('WebSocket Disconnected!', event)
            }
            if (!toast.isShown()) {
                setTimeout(function () {
                    disconnected = true
                    $('#disconnected-toast-title')
                        .removeClass('text-warning')
                        .addClass('text-danger')
                        .text('Reconnecting...')
                    toast.show()
                }, 2 * 1000)
            }
        }
        setTimeout(function () {
            wsConnect()
        }, 2 * 1000)
    }
    socket.onerror = function (event) {
        if (!disconnected) {
            console.error('WebSocket Error:', event)
        }
    }
    initListener()
}

// File Events

const EVENT_HANDLERS = {
    'file-new': messageNewFile,
    'set-expr-file': messageExpire,
    'toggle-private-file': messageTogglePrivate,
    'set-password-file': messagePassword,
    'file-delete': messageDelete,
    'file-update': messageFileUpdate,
    'set-file-name': messageFileRename,
    'stream-status': messageStreamStatus,
    'set-stream-title': messageStreamTitleUpdate,
    'set-stream-description': messageStreamDescriptionUpdate,
    'toggle-public-stream': messageTogglePublicStream,
    'album-delete': messageAlbumDelete,
    'album-new': messageAlbumNew,
    'toggle-private-album': messageTogglePrivateAlbum,
    message: messageToast,
}

function initListener() {
    if (_initializedSockets.has(socket)) return
    _initializedSockets.add(socket)
    socket.addEventListener('message', function (event) {
        if (event.data === 'pong') return
        let data
        try {
            data = JSON.parse(event.data)
        } catch (e) {
            console.error('WebSocket: failed to parse message', event.data, e)
            return
        }
        const handler = EVENT_HANDLERS[data.event]
        if (handler) {
            handler(data)
        } else {
            console.warn('WebSocket: unhandled event', data.event)
        }
    })
}

// Batched toast: accumulates events within `delay` ms; shows individual toasts
// for 1-2 events, summary for 3+. batchKey groups events of the same type+user.
const _toastBatches = {}
function batchedToast(batchKey, singleMsg, summaryFn, delay = 500) {
    const batch = _toastBatches[batchKey] || { count: 0, singleMsg }
    batch.count++
    _toastBatches[batchKey] = batch
    clearTimeout(batch.timer)
    batch.timer = setTimeout(() => {
        delete _toastBatches[batchKey]
        const msg = batch.count >= 3 ? summaryFn(batch.count) : batch.singleMsg
        show_toast(typeof msg === 'function' ? msg() : msg)
    }, delay)
}

// Socket Handlers
// these handlers are dual purpose and used across a variety of pages

function messageFileRename(data) {
    show_toast(
        `${truncateName(data.old_name)} renamed to ${truncateName(data.name)}`
    )
}

function messageExpire(data) {
    data.objects.forEach((element) => {
        console.debug('messageExpire:', element)
        const expireText = $(`#file-${element.id} .expire-value`)
        const expireIcon = $(`#file-${element.id} .expire-icon`)
        if (element.expr) {
            expireText.text(element.expr).data('clipboard-text', element.expr)
            expireIcon.attr('title', `File Expires in ${element.expr}`).show()
        } else {
            expireText.text('Never').data('clipboard-text', 'Never')
            expireIcon.attr('title', 'No Expiration').hide()
        }
    })
    if (data.objects.length >= 3) {
        show_toast(
            `${data.objects.length} file expirations updated.`,
            'success'
        )
    } else {
        data.objects.forEach((element) => {
            const msg = element.expr
                ? `${truncateName(element.name)} - Expire set to: ${element.expr}`
                : `${truncateName(element.name)} - Cleared Expiration.`
            show_toast(msg, 'success')
        })
    }
}

function messagePrivate(data) {
    console.log('messagePrivate:', data)
    const privateStatus = $(`#file-${data.id} .privateStatus`)
    const previewIcon = $(`#previewIcon`)
    const ctxPrivateText = $(`.ctx-menu[data-id="${data.id}"] .privateText`)
    const ctxPrivateIcon = $(`.ctx-menu[data-id="${data.id}"] .privateIcon`)
    if (data.private) {
        privateStatus.removeClass('d-none')
        previewIcon.removeClass('d-none').show()
        ctxPrivateText.text('Make Public')
        ctxPrivateIcon.removeClass('fa-lock').addClass('fa-lock-open')
        show_toast(`File ${truncateName(data.name)} set to private.`, 'success')
    } else {
        privateStatus.addClass('d-none')
        previewIcon.addClass('d-none').hide()
        ctxPrivateText.text('Make Private')
        ctxPrivateIcon.removeClass('fa-lock-open').addClass('fa-lock')
        show_toast(`File ${truncateName(data.name)} set to public.`, 'success')
    }
}

function messagePassword(data) {
    console.log('messagePassword', data)
    const passwordStatus = $(`#file-${data.id} .passwordStatus`)
    if (data.password) {
        passwordStatus.removeClass('d-none')
        show_toast(`Password set for ${truncateName(data.name)}`, 'success')
    } else {
        passwordStatus.addClass('d-none')
        show_toast(`Password unset for ${truncateName(data.name)}`, 'success')
    }
}

// file-update fires from the Files post_save signal for any field change.
// Specific events (toggle-private-file, set-expr-file, set-password-file,
// set-file-name) already handle their own toasts and DOM updates; this
// handler exists so the catch-all 'unhandled event' warning doesn't fire.
// The files DataTable refreshes its row data via the extra map in
// file-table.js so derived column renderers stay in sync.
function messageFileUpdate(_data) {
    // intentionally empty — see comment above
}

function messageDelete(data) {
    batchedToast(
        `file-delete:${data.user_name}`,
        `${truncateName(data.name)} deleted by ${data.user_name}.`,
        (n) => `${n} files deleted by ${data.user_name}.`
    )
}

function messageAlbumDelete(data) {
    batchedToast(
        `album-delete:${data.user_name}`,
        `"${truncateName(data.name)}" Album deleted by ${data.user_name}.`,
        (n) => `${n} albums deleted by ${data.user_name}.`
    )
}

function messageAlbumNew(data) {
    batchedToast(
        `album-new:${data.user_name}`,
        `"${truncateName(data.name)}" Album created by ${data.user_name}.`,
        (n) => `${n} albums created by ${data.user_name}.`
    )
}

function messageTogglePrivateAlbum(data) {
    if (data.objects.length >= 3) {
        const label = data.objects[0].private ? 'private' : 'public'
        show_toast(`${data.objects.length} albums set to ${label}.`, 'success')
    } else {
        data.objects.forEach((album) => {
            const label = album.private ? 'private' : 'public'
            show_toast(
                `"${truncateName(album.name)}" set to ${label}.`,
                'success'
            )
        })
    }
}

function messageNewFile(data) {
    batchedToast(
        `file-new:${data.user_name}`,
        () => {
            const link = $('<a>', {
                href: data.url,
                class: 'link-light fw-semibold',
                text: truncateName(data.name),
            })
            return $('<span>')
                .append(link)
                .append(
                    document.createTextNode(` uploaded by ${data.user_name}.`)
                )
        },
        (n) => `${n} files uploaded by ${data.user_name}.`
    )
}

function messageTogglePrivate(data) {
    const objects = 'objects' in data ? data.objects : [data]
    objects.forEach(messagePrivate)
}

function messageToast(data) {
    const bsClass = data.bsClass || 'info'
    const delay = data.delay || 6000
    show_toast(data.message, bsClass, delay)
}

function messageStreamStatus(data) {
    const badge = document.getElementById('stream-status-badge')
    if (!badge) return
    const streamNameEl = document.querySelector('[data-stream-name]')
    if (streamNameEl && streamNameEl.dataset.streamName !== data.name) return
    if (data.is_live) {
        badge.className = 'm-0 text-danger fw-bold text-glow'
        badge.textContent = 'Live'
        document.getElementById('stream-ended-at')?.remove()
        if (data.started_at) {
            const el = document.getElementById('stream-started-at')
            if (el) {
                const date = new Date(data.started_at)
                const formatted = date.toLocaleString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                    hour: 'numeric',
                    minute: '2-digit',
                    hour12: true,
                    timeZoneName: 'short',
                })
                el.innerHTML = `<strong>Started:</strong> ${formatted}`
            }
        }
    } else {
        badge.className = 'm-0 text-secondary fw-bold'
        badge.textContent = 'Offline'
        if (data.ended_at && !document.getElementById('stream-ended-at')) {
            const date = new Date(data.ended_at)
            const formatted = date.toLocaleString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric',
                hour: 'numeric',
                minute: '2-digit',
                hour12: true,
                timeZoneName: 'short',
            })
            const p = document.createElement('p')
            p.id = 'stream-ended-at'
            p.className = 'm-0 m-1'
            p.innerHTML = `<strong>Ended:</strong> ${formatted}`
            badge
                .closest('.row')
                ?.nextElementSibling?.querySelector('.col-sm')
                ?.appendChild(p)
        }
    }
}

function messageStreamTitleUpdate(data) {
    show_toast(`Stream title updated to "${data.title}"`)
}

function messageStreamDescriptionUpdate(_data) {
    show_toast(`Stream description updated.`)
}

function messageTogglePublicStream(data) {
    if (data.objects.length >= 3) {
        const label = data.objects[0].public ? 'public' : 'private'
        show_toast(`${data.objects.length} streams set to ${label}.`, 'success')
    } else {
        data.objects.forEach((s) => {
            const label = s.public ? 'public' : 'private'
            show_toast(`Stream "${s.name}" set to ${label}.`, 'success')
        })
    }
}

function truncateName(filename) {
    if (filename.length && filename.length > 42) {
        return filename.substring(0, 40) + '...'
    }
    return filename
}

/**
 * Subscribes a DataTable to socket-driven new/delete events. Optional `extra`
 * map handles event names that don't fit the simple add/delete shape (e.g.
 * file rename). Uses the DataTables row API for delete so internal state
 * stays consistent.
 *
 *   attachSocketTableSync(albumsDataTable, {
 *       newEvent: 'album-new',
 *       deleteEvent: 'album-delete',
 *       idPrefix: 'album',
 *       addRow: loader.addRow,
 *       countEl: totalAlbumsCount,
 *       maxRows: isHome ? 10 : null,
 *       onOverflow: () => warn.classList.remove('d-none'),
 *   })
 *
 * @param {any} dt DataTables API instance.
 * @param {object} opts
 */
export function attachSocketTableSync(dt, opts) {
    socket?.addEventListener('message', function (event) {
        if (event.data === 'pong') return
        let data
        try {
            data = JSON.parse(event.data)
        } catch {
            return
        }
        if (data.event === opts.deleteEvent) {
            const row = dt.row(`#${opts.idPrefix}-${data.id}`)
            if (row.node()) row.remove().draw(false)
            if (opts.countEl) opts.countEl.textContent = dt.rows().count()
        } else if (data.event === opts.newEvent) {
            if (opts.maxRows && dt.rows().count() >= opts.maxRows) {
                opts.onOverflow?.()
                return
            }
            opts.addRow(data)
        } else if (opts.extra?.[data.event]) {
            opts.extra[data.event](data)
        }
    })
}
