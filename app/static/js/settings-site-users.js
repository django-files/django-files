import { fetchUsers } from './api-fetch.js'
import {
    dtRevealThead,
    noChromeLayout,
    paginatedTableDefaults,
} from './table-defaults.js'

const usersTable = $('#users-table')
const editUserModalEl = document.getElementById('edit-user-modal')
const editUserForm = document.getElementById('editUserForm')

let usersDataTable
let nextPage = 1
let fetchLock = false

const dataTablesOptions = {
    ...paginatedTableDefaults,
    order: [1, 'asc'],
    layout: noChromeLayout,
    columns: [
        { data: 'id' },
        { data: 'username' },
        { data: 'storage_usage' },
        { data: 'id' },
    ],
    columnDefs: [
        {
            targets: 0,
            visible: false,
        },
        {
            targets: 1,
            render: renderUser,
            responsivePriority: 1,
        },
        {
            targets: 2,
            render: renderStorage,
            responsivePriority: 2,
            width: '220px',
        },
        {
            targets: 3,
            render: renderActions,
            responsivePriority: 1,
            orderable: false,
            width: '28px',
        },
    ],
}

const PROVIDER_ICONS = {
    discord: '<i class="fab fa-discord" title="Discord"></i>',
    github: '<i class="fab fa-github" title="GitHub"></i>',
    google: '<i class="fab fa-google" title="Google"></i>',
}

function renderUser(data, type, row) {
    if (type === 'filter') return `${row.username} ${row.first_name || ''}`
    if (type !== 'display') return data
    const name = row.first_name || row.username
    const adminBadge = row.is_superuser
        ? '<span class="badge text-bg-warning ms-2">Admin</span>'
        : ''
    const sub =
        row.first_name && row.first_name !== row.username
            ? `<div class="text-body-secondary small">@${row.username}</div>`
            : ''
    const providerIcons = (row.oauth_providers || [])
        .map((p) => PROVIDER_ICONS[p] || '')
        .join('')
    const providers = providerIcons
        ? `<span class="ms-2 d-inline-flex gap-1 text-body-secondary small">${providerIcons}</span>`
        : ''
    return `<div class="d-flex align-items-center gap-2">
        <img src="${row.avatar_url}" class="rounded-circle flex-shrink-0"
             style="width:32px;height:32px;object-fit:cover;" alt="${name}">
        <div><div>${name}${adminBadge}${providers}</div>${sub}</div>
    </div>`
}

function formatBytes(bytes) {
    if (!bytes) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return (
        Number.parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
    )
}

function renderStorage(data, type, row) {
    if (type !== 'display') return row.storage_usage
    const used = formatBytes(row.storage_usage)
    if (!row.storage_quota) return `<span>${used}</span>`
    const total = formatBytes(row.storage_quota)
    const pct = Math.min(
        100,
        Math.round((row.storage_usage / row.storage_quota) * 100)
    )
    let cls = ''
    if (pct > 95) cls = 'bg-danger'
    else if (pct > 85) cls = 'bg-warning'
    return `<div class="small">${used} / ${total} (${pct}%)</div>
            <div class="progress mt-1" style="height:5px;">
                <div class="progress-bar ${cls}" style="width:${pct}%;"></div>
            </div>`
}

function renderActions(data, type, row) {
    if (type !== 'display') return data
    return `<a role="button" class="editUserBtn" title="Edit" data-user-id="${row.id}">
        <i class="fa-solid fa-pen-to-square link-body-emphasis"></i></a>`
}

async function addUserRows() {
    if (!fetchLock) {
        fetchLock = true
        const data = await fetchUsers(nextPage)
        nextPage = data.next
        for (const user of data.users) {
            user['DT_RowId'] = `user-${user.id}`
            usersDataTable.row.add(user).draw(false)
        }
        fetchLock = false
    }
}

function showUsersSkeletons(count = 5) {
    const tbody = document.querySelector('#users-table tbody')
    if (!tbody) return
    buildSkeletonRows(tbody, count, [
        { w: 0 },
        { w: 160 },
        { w: 120 },
        { w: 24 },
    ])
}

usersTable.on('click', '.editUserBtn', (event) => {
    const userId = event.currentTarget.dataset.userId
    const row = usersDataTable.row(`#user-${userId}`).data()
    if (!row) return
    editUserForm.reset()
    document.getElementById('edit-user-id').value = row.id
    document.getElementById('edit-user-name').textContent =
        row.first_name || row.username
    document.getElementById('edit-user-storage-quota').value =
        row.storage_quota_human_read || ''
    bootstrap.Modal.getOrCreateInstance(editUserModalEl).show()
})

editUserForm?.addEventListener('submit', async (event) => {
    event.preventDefault()
    const userId = document.getElementById('edit-user-id').value
    const storageQuota = document.getElementById(
        'edit-user-storage-quota'
    ).value
    const response = await fetch(`/api/user/${userId}/`, {
        method: 'PATCH',
        body: JSON.stringify({ storage_quota: storageQuota }),
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json',
        },
    })
    if (response.ok) {
        const data = await response.json()
        const row = usersDataTable.row(`#user-${userId}`)
        row.data({ ...row.data(), ...data }).draw(false)
        bootstrap.Modal.getOrCreateInstance(editUserModalEl).hide()
        show_toast('User updated.', 'success')
    } else {
        const data = await response.json().catch(() => ({}))
        show_toast(data.error || 'Failed to update user.', 'danger')
    }
})

document.addEventListener('DOMContentLoaded', async () => {
    usersDataTable = usersTable.DataTable(dataTablesOptions)
    wireToolbarSearch('users-search-input', usersDataTable)
    await initDataTable(
        usersDataTable,
        showUsersSkeletons,
        addUserRows,
        'No users found',
        'No matching users found'
    )
    dtRevealThead(usersDataTable)
    while (nextPage) {
        await addUserRows()
    }
})
