// Webhook management on the user settings page

console.debug('LOADING: settings-user-webhooks.js')

const webhookModalEl = document.getElementById('webhookModal')
const webhookForm = document.getElementById('webhookForm')
const deleteWebhookModalEl = document.getElementById('deleteWebhookModal')

let deleteWebhookID

document.getElementById('addWebhookBtn')?.addEventListener('click', () => {
    webhookForm.reset()
    document.getElementById('webhook-id').value = ''
    document.getElementById('webhookModalLabel').textContent = 'Add Webhook'
    updateSecretVisibility()
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
        document.getElementById('webhookModalLabel').textContent =
            'Edit Webhook'
        updateSecretVisibility()
        bootstrap.Modal.getOrCreateInstance(webhookModalEl).show()
    })
)

document
    .getElementById('webhook-type')
    ?.addEventListener('change', updateSecretVisibility)

webhookForm?.addEventListener('submit', async (event) => {
    event.preventDefault()
    const webhookID = document.getElementById('webhook-id').value
    const body = {
        name: document.getElementById('webhook-name').value,
        webhook_type: document.getElementById('webhook-type').value,
        url: document.getElementById('webhook-url').value,
        secret: document.getElementById('webhook-secret').value,
        active: document.getElementById('webhook-active').checked,
        events: [...document.querySelectorAll('.webhook-event-check')]
            .filter((check) => check.checked)
            .map((check) => check.value),
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

function updateSecretVisibility() {
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
