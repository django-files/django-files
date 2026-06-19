import { fetchTokens } from './api-fetch.js'
import { noChromeLayout, paginatedTableDefaults } from './table-defaults.js'

const tokenTable = $('#token-table')

let tokensDataTable

const dataTablesOptions = {
    ...paginatedTableDefaults,
    order: [2, 'desc'],
    layout: noChromeLayout,
    columns: [
        { data: 'name' },
        { data: 'user_agent' },
        { data: 'created_at' },
        { data: 'last_used_at' },
        { data: 'created_ip' },
        { data: 'expires_at' },
        { data: 'is_active' },
        { data: 'id' },
    ],
    columnDefs: [
        {
            targets: 0,
            render: renderName,
            responsivePriority: 1,
        },
        {
            targets: 1,
            render: renderUserAgent,
            responsivePriority: 3,
        },
        {
            targets: 2,
            render: renderDate,
            responsivePriority: 4,
        },
        {
            targets: 3,
            render: renderLastUsed,
            responsivePriority: 5,
        },
        {
            targets: 4,
            render: renderIP,
            responsivePriority: 6,
        },
        {
            targets: 5,
            render: renderExpiry,
            responsivePriority: 3,
        },
        {
            targets: 6,
            render: renderStatus,
            responsivePriority: 2,
        },
        {
            targets: 7,
            render: renderActions,
            responsivePriority: 1,
            orderable: false,
        },
    ],
}

function renderName(data) {
    if (!data) return '<span class="text-muted">—</span>'
    return `<span class="fw-medium">${data}</span>`
}

function formatUA(uaString) {
    if (!uaString) return null
    if (typeof UAParser === 'undefined') return null
    const r = new UAParser(uaString).getResult()
    const isMobile = ['mobile', 'tablet'].includes(r.device?.type)
    if (isMobile) {
        const ver = r.os?.version ? ` ${r.os.version}` : ''
        return r.os?.name ? `${r.os.name}${ver}` : null
    }
    const parts = []
    if (r.browser?.name) parts.push(r.browser.name)
    if (r.os?.name) parts.push(r.os.name)
    return parts.length ? parts.join(' / ') : null
}

function renderUserAgent(data) {
    if (!data) return '<span class="text-muted">—</span>'
    const label = formatUA(data) ?? data.slice(0, 50)
    return `<span title="${data.replace(/"/g, '&quot;')}" class="text-muted small">${label}</span>`
}

function renderDate(data) {
    if (!data) return ''
    const date = new Date(data)
    return date.toLocaleString()
}

function renderLastUsed(data) {
    if (!data) return '<span class="text-muted">Never</span>'
    const date = new Date(data)
    const hours = Math.floor((Date.now() - date) / 36e5)
    let label
    if (hours < 1) {
        label = 'in the last hour'
    } else if (hours < 24) {
        label = `${hours} hour${hours === 1 ? '' : 's'} ago`
    } else {
        const days = Math.floor(hours / 24)
        label = `${days} day${days === 1 ? '' : 's'} ago`
    }
    return `<span title="${date.toLocaleString()}">${label}</span>`
}

function renderIP(data) {
    if (!data) return '<span class="text-muted">Unknown</span>'
    return data
}

function renderExpiry(data) {
    if (!data) return '<span class="text-muted">Never</span>'
    const date = new Date(data)
    return date.toLocaleDateString()
}

function renderStatus(data, type, row) {
    if (type !== 'display') return data ? 'active' : 'inactive'
    if (!row.is_active)
        return '<span class="badge text-bg-secondary">Disabled</span>'
    if (row.expires_at && new Date(row.expires_at) < new Date())
        return '<span class="badge text-bg-warning text-dark">Expired</span>'
    return '<span class="badge text-bg-success">Active</span>'
}

function renderActions(data, type, row) {
    if (type !== 'display') return data
    const toggleIcon = row.is_active ? 'fa-ban' : 'fa-circle-check'
    const toggleTitle = row.is_active ? 'Disable token' : 'Enable token'
    const toggleClass = row.is_active
        ? 'btn-outline-warning'
        : 'btn-outline-success'
    return `
        <button class="btn btn-sm ${toggleClass} toggle-token-btn me-1"
                data-token-id="${data}" title="${toggleTitle}">
            <i class="fa-solid ${toggleIcon}"></i>
        </button>
        <button class="btn btn-sm btn-outline-danger delete-token-btn"
                data-token-id="${data}" title="Delete token">
            <i class="fa-solid fa-trash"></i>
        </button>`
}

function showTokensSkeletons(count = 5) {
    const tbody = document.querySelector('#token-table tbody')
    if (!tbody) return
    buildSkeletonRows(tbody, count, [
        { w: 120 },
        { w: 100 },
        { w: 80 },
        { w: 80 },
        { w: 100 },
        { w: 80 },
        { w: 60 },
        { w: 50 },
    ])
}

function wireToolbarSearch(inputId, dt) {
    const input = document.getElementById(inputId)
    if (!input || !dt) return
    let timer
    input.addEventListener('input', () => {
        clearTimeout(timer)
        timer = setTimeout(() => dt.search(input.value).draw(), 300)
    })
}

async function toggleToken(tokenId) {
    try {
        const response = await fetch(`/api/token/${tokenId}/`, {
            method: 'PATCH',
            headers: { 'X-CSRFToken': csrftoken },
        })
        if (!response.ok) throw new Error('Failed to toggle token')
        const data = await response.json()
        const row = document.getElementById(`token-${tokenId}`)
        if (row) {
            const dtRow = tokensDataTable.row(row)
            const rowData = dtRow.data()
            rowData.is_active = data.is_active
            dtRow.data(rowData).draw(false)
        }
        show_toast(
            data.is_active ? 'Token enabled' : 'Token disabled',
            'success'
        )
    } catch (error) {
        console.error('Error toggling token:', error)
        show_toast('Failed to update token', 'danger')
    }
}

let pendingDeleteId = null

function openDeleteTokenModal(tokenId) {
    pendingDeleteId = tokenId
    const modal = new bootstrap.Modal(
        document.getElementById('modal-delete-token')
    )
    modal.show()
}

async function deleteToken(tokenId) {
    try {
        const response = await fetch(`/api/token/${tokenId}/`, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': csrftoken },
        })
        if (!response.ok) throw new Error('Failed to delete token')
        const row = document.getElementById(`token-${tokenId}`)
        if (row) tokensDataTable.row(row).remove().draw(false)
        show_toast('Token deleted', 'success')
    } catch (error) {
        console.error('Error deleting token:', error)
        show_toast('Failed to delete token', 'danger')
    }
}

function setupTokenButtons() {
    document.querySelectorAll('.toggle-token-btn').forEach((btn) => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault()
            await toggleToken(btn.dataset.tokenId)
        })
    })
    document.querySelectorAll('.delete-token-btn').forEach((btn) => {
        btn.addEventListener('click', (e) => {
            e.preventDefault()
            openDeleteTokenModal(btn.dataset.tokenId)
        })
    })
}

function openNewTokenModal() {
    const modal = new bootstrap.Modal(
        document.getElementById('modal-new-token')
    )
    modal.show()
}

function fadeOut(el, duration = 180) {
    return new Promise((resolve) => {
        el.style.transition = `opacity ${duration}ms ease-in-out`
        el.style.opacity = '0'
        setTimeout(() => {
            el.classList.add('d-none')
            el.style.transition = ''
            el.style.opacity = ''
            resolve()
        }, duration)
    })
}

function fadeIn(el, duration = 180) {
    el.classList.remove('d-none')
    el.style.opacity = '0'
    el.style.transition = `opacity ${duration}ms ease-in-out`
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            el.style.opacity = '1'
        })
    })
}

function resetNewTokenModal() {
    const form = document.getElementById('new-token-form')
    const formFields = document.getElementById('new-token-form-fields')
    const formButtons = document.getElementById('new-token-form-buttons')
    const resultDiv = document.getElementById('new-token-result')
    const dismissBtn = document.getElementById('new-token-dismiss-btn')
    const expirySelect = document.getElementById('token-expiry-select')
    const customDate = document.getElementById('token-custom-date')

    form?.reset()
    expirySelect && (expirySelect.value = 'never')
    customDate && (customDate.value = '')
    customDate?.classList.add('d-none')
    customDate?.parentElement?.classList.add('d-none')

    formFields?.classList.remove('d-none')
    formFields && (formFields.style.opacity = '')
    formButtons?.classList.remove('d-none')
    formButtons && (formButtons.style.opacity = '')
    resultDiv?.classList.add('d-none')
    resultDiv && (resultDiv.style.opacity = '')
    dismissBtn?.classList.add('d-none')
    dismissBtn && (dismissBtn.style.opacity = '')
}

function handleNewTokenSubmit() {
    const form = document.getElementById('new-token-form')
    if (!form) return

    let tokenJustCreated = false
    const modalEl = document.getElementById('modal-new-token')
    modalEl?.addEventListener('hidden.bs.modal', async () => {
        resetNewTokenModal()
        if (tokenJustCreated) {
            tokenJustCreated = false
            await loadTokens(1)
        }
    })

    form.addEventListener('submit', async (e) => {
        e.preventDefault()
        const name = document.getElementById('token-name').value
        const expirySelect = document.getElementById('token-expiry-select')
        const customDate = document.getElementById('token-custom-date')

        let expires_at = null
        if (expirySelect.value !== 'never') {
            if (expirySelect.value === 'custom') {
                expires_at = customDate.value
                    ? new Date(customDate.value).toISOString()
                    : null
            } else {
                const days = parseInt(expirySelect.value)
                if (days > 0) {
                    const date = new Date()
                    date.setDate(date.getDate() + days)
                    expires_at = date.toISOString()
                }
            }
        }

        try {
            const response = await fetch('/api/token/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken,
                },
                body: JSON.stringify({ name, expires_at }),
            })

            if (!response.ok) throw new Error('Failed to create token')

            const data = await response.json()
            const token = data.token

            const formFields = document.getElementById('new-token-form-fields')
            const formButtons = document.getElementById(
                'new-token-form-buttons'
            )
            const resultDiv = document.getElementById('new-token-result')
            const tokenDisplay = document.getElementById('new-token-display')
            const copyBtn = document.getElementById('new-token-copy-btn')
            const dismissBtn = document.getElementById('new-token-dismiss-btn')

            tokenDisplay.textContent = token
            copyBtn.onclick = async () => {
                await navigator.clipboard.writeText(token)
                show_toast('Token copied to clipboard', 'info')
            }

            await Promise.all([fadeOut(formFields), fadeOut(formButtons)])
            fadeIn(resultDiv)
            fadeIn(dismissBtn)

            tokenJustCreated = true
            show_toast('Token created successfully', 'success')
        } catch (error) {
            console.error('Error creating token:', error)
            show_toast('Failed to create token', 'danger')
        }
    })
}

function handleExpirySelectChange() {
    const expirySelect = document.getElementById('token-expiry-select')
    const customDateWrapper =
        document.getElementById('token-custom-date')?.parentElement
    const customDate = document.getElementById('token-custom-date')

    if (!expirySelect || !customDateWrapper || !customDate) return

    expirySelect.addEventListener('change', (e) => {
        if (e.target.value === 'custom') {
            customDateWrapper.classList.remove('d-none')
            customDate.classList.remove('d-none')
        } else {
            customDateWrapper.classList.add('d-none')
            customDate.classList.add('d-none')
        }
    })
}

async function loadTokens(page) {
    const data = await fetchTokens(page)
    for (const token of data.tokens) {
        token['DT_RowId'] = `token-${token.id}`
        tokensDataTable.row.add(token).draw(false)
    }
    if (data.page < data.num_pages) {
        await loadTokens(data.page + 1)
    }
    setupTokenButtons()
}

document.addEventListener('DOMContentLoaded', async () => {
    if (!tokenTable.length) return

    tokensDataTable = tokenTable.DataTable(dataTablesOptions)
    wireToolbarSearch('token-search', tokensDataTable)
    showTokensSkeletons()
    await loadTokens(1)

    document.getElementById('btn-new-token').addEventListener('click', (e) => {
        e.preventDefault()
        openNewTokenModal()
    })

    document
        .getElementById('confirm-delete-token-btn')
        ?.addEventListener('click', async () => {
            const modal = bootstrap.Modal.getInstance(
                document.getElementById('modal-delete-token')
            )
            modal?.hide()
            if (pendingDeleteId) {
                await deleteToken(pendingDeleteId)
                pendingDeleteId = null
            }
        })

    handleExpirySelectChange()
    handleNewTokenSubmit()
})
