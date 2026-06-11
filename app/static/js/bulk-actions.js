// Shared helpers for bulk-action support on DataTables (albums, shorts, etc.).
// Files uses its own richer bulk menu — see file-table.js.

// Toggle the toolbar's #bulk-actions dropdown disabled state based on row
// selection in the given DataTable.
export function initBulkSelect(dt, btnId = 'bulk-actions') {
    const btn = document.getElementById(btnId)
    if (!btn) return
    dt.on('select', () => {
        btn.disabled = false
    })
    dt.on('deselect', () => {
        if (dt.rows({ selected: true }).count() === 0) btn.disabled = true
    })
}

// Collect PKs from the DataTable's selected rows.
export function selectedPks(dt, pkField = 'id') {
    const pks = []
    dt.rows('.selected').every(function () {
        pks.push(this.data()[pkField])
    })
    return pks
}

// Wire a shared "delete N items" confirmation modal to both single-row and
// bulk triggers. The modal's body text is set dynamically based on count.
//
// opts:
//   modalId       — id of the bootstrap modal element
//   bodyId        — id of the modal body element (text will be replaced)
//   confirmId     — id of the confirm button
//   entity        — singular noun, e.g. "album"
//   entityPlural  — plural form (defaults to entity + "s")
//   onConfirm(pks) — async/sync callback; modal is hidden when it resolves
//
// Returns { open(pks) } so callers can trigger the modal from any flow.
export function wireDeleteModal(opts) {
    const modalEl = document.getElementById(opts.modalId)
    const modal = modalEl ? bootstrap.Modal.getOrCreateInstance(modalEl) : null
    const bodyEl = document.getElementById(opts.bodyId)
    const confirmBtn = document.getElementById(opts.confirmId)
    const plural = opts.entityPlural || `${opts.entity}s`
    let pending = []

    function open(pks) {
        pending = pks
        if (bodyEl) {
            bodyEl.textContent =
                pks.length === 1
                    ? `Are you sure you want to delete this ${opts.entity}?`
                    : `Are you sure you want to delete ${pks.length} ${plural}?`
        }
        modal?.show()
    }

    confirmBtn?.addEventListener('click', async function () {
        if (!pending.length) return
        const pks = pending
        pending = []
        try {
            await opts.onConfirm(pks)
        } finally {
            modal?.hide()
        }
    })

    return { open }
}
