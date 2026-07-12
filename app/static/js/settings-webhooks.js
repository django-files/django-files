// Webhook management, shared by the user and site settings pages.
// The hidden #webhook-scope input (rendered per page) fixes the scope:
// "user" on user settings, "site" on site settings.

console.debug('LOADING: settings-webhooks.js')

const webhookModalEl = document.getElementById('webhookModal')
const webhookForm = document.getElementById('webhookForm')
const deleteWebhookModalEl = document.getElementById('deleteWebhookModal')

let deleteWebhookID

document.getElementById('addWebhookBtn')?.addEventListener('click', () => {
    webhookForm.reset()
    document.getElementById('webhook-id').value = ''
    document.getElementById('webhookModalLabel').textContent = 'Add Webhook'
    updateTypeFields()
    bootstrap.Modal.getOrCreateInstance(webhookModalEl).show()
})

document.querySelectorAll('.editWebhookBtn').forEach((el) =>
    el.addEventListener('click', (event) => {
        const data = event.currentTarget.dataset
        webhookForm.reset()
        document.getElementById('webhook-id').value = data.webhookId
        document.getElementById('webhook-name').value = data.webhookName
        document.getElementById('webhook-type').value = data.webhookType
        document.getElementById('webhook-url').value = data.webhookUrl
        document.getElementById('webhook-secret').value = data.webhookSecret
        document.getElementById('webhook-active').checked =
            data.webhookActive === 'true'
        const events = data.webhookEvents ? data.webhookEvents.split(',') : []
        document
            .querySelectorAll('.webhook-event-check')
            .forEach((check) => (check.checked = events.includes(check.value)))
        document.getElementById('webhook-tag-filter').value =
            data.webhookTagFilter || ''
        document.getElementById('webhookModalLabel').textContent =
            'Edit Webhook'
        updateTypeFields()
        bootstrap.Modal.getOrCreateInstance(webhookModalEl).show()
    })
)

document
    .getElementById('webhook-type')
    ?.addEventListener('change', updateTypeFields)

webhookForm?.addEventListener('submit', async (event) => {
    event.preventDefault()
    const webhookID = document.getElementById('webhook-id').value
    const filterTags = document
        .getElementById('webhook-tag-filter')
        .value.split(',')
        .map((tag) => tag.trim())
        .filter(Boolean)
    const body = {
        name: document.getElementById('webhook-name').value,
        webhook_type: document.getElementById('webhook-type').value,
        scope: document.getElementById('webhook-scope').value,
        url: document.getElementById('webhook-url').value,
        secret: document.getElementById('webhook-secret').value,
        active: document.getElementById('webhook-active').checked,
        events: [...document.querySelectorAll('.webhook-event-check')]
            .filter((check) => check.checked)
            .map((check) => check.value),
        filters: filterTags.length ? { tags: filterTags } : {},
    }
    const url = webhookID ? `/api/webhooks/${webhookID}/` : '/api/webhooks/'
    const method = webhookID ? 'PATCH' : 'POST'
    const response = await fetch(url, {
        method,
        body: JSON.stringify(body),
        headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json',
        },
    })
    if (response.ok) {
        bootstrap.Modal.getOrCreateInstance(webhookModalEl).hide()
        show_toast(`Webhook ${webhookID ? 'Updated' : 'Created'}.`, 'success')
        location.reload()
    } else {
        await webhookErrorToast(response)
    }
})

document.querySelectorAll('.deleteWebhookBtn').forEach((el) =>
    el.addEventListener('click', (event) => {
        deleteWebhookID = event.currentTarget.dataset.webhookId
        bootstrap.Modal.getOrCreateInstance(deleteWebhookModalEl).show()
    })
)

document
    .getElementById('confirmDeleteWebhookBtn')
    ?.addEventListener('click', async () => {
        const response = await fetch(`/api/webhooks/${deleteWebhookID}/`, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': csrftoken },
        })
        bootstrap.Modal.getOrCreateInstance(deleteWebhookModalEl).hide()
        if (response.ok) {
            const table = document.getElementById('webhooksTable')
            const rowCount = table?.querySelectorAll('tr').length ?? 0
            document.getElementById(`webhook-${deleteWebhookID}`)?.remove()
            if (rowCount <= 2) table?.remove()
            show_toast('Webhook Deleted.', 'success')
        } else {
            await webhookErrorToast(response)
        }
    })

document.querySelectorAll('.testWebhookBtn').forEach((el) =>
    el.addEventListener('click', async (event) => {
        const webhookID = event.currentTarget.dataset.webhookId
        const response = await fetch(`/api/webhooks/${webhookID}/test/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrftoken },
        })
        if (!response.ok) {
            await webhookErrorToast(response)
            return
        }
        const data = await response.json()
        if (data.success) {
            show_toast(`Test Delivered: HTTP ${data.status_code}`, 'success')
        } else {
            const reason = data.error ?? `HTTP ${data.status_code}`
            show_toast(`Test Failed: ${reason}`, 'danger')
        }
    })
)

// A webhook authorized via the Discord OAuth flow is staged in the session and
// finished here: open the modal pre-filled so the user picks events, then the
// normal save path creates it.
document.addEventListener('DOMContentLoaded', () => {
    const pendingWebhookEl = document.getElementById('pending-webhook-data')
    if (!pendingWebhookEl || !webhookForm) return
    const pending = JSON.parse(pendingWebhookEl.textContent)
    webhookForm.reset()
    document.getElementById('webhook-id').value = ''
    document.getElementById('webhook-name').value = pending.name
    document.getElementById('webhook-type').value = 'discord'
    document.getElementById('webhook-url').value = pending.url
    document
        .querySelectorAll('.webhook-event-check')
        .forEach((check) => (check.checked = check.value === 'file.upload'))
    document.getElementById('webhookModalLabel').textContent =
        'Finish Discord Webhook'
    updateTypeFields()
    bootstrap.Modal.getOrCreateInstance(webhookModalEl).show()
})

function updateTypeFields() {
    const isCustom = document.getElementById('webhook-type').value === 'custom'
    document
        .getElementById('webhook-secret-group')
        .classList.toggle('d-none', !isCustom)
}

async function webhookErrorToast(response) {
    let message
    try {
        const data = await response.json()
        message = data.error
            ? `${response.status}: ${data.error}`
            : `${response.status}: ${response.statusText}`
    } catch {
        message = `${response.status}: ${response.statusText}`
    }
    show_toast(message, 'danger')
}
